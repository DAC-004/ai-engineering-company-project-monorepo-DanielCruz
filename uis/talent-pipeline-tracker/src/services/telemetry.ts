/**
 * Central HealthCore telemetry capture service.
 *
 * Components call `track()` only. This module owns envelope fields, the
 * in-memory queue, 10s / 20-event batching, sendBeacon flush, and retry.
 * Delivery failures must never throw to the caller.
 */

import {
  getOrCreateTelemetrySessionId,
  getTelemetryUserId,
} from "@/lib/telemetry/identity";
import {
  EVENT_PROPERTY_ALLOWLIST,
  EVENT_REQUIRED_PROPERTIES,
  isTelemetryEventType,
  TELEMETRY_SCHEMA_VERSION,
  type TelemetryEventType,
} from "@/lib/telemetry/schema";

export const TELEMETRY_FLUSH_INTERVAL_MS = 10_000;
export const TELEMETRY_MAX_BATCH_SIZE = 20;
export const TELEMETRY_MAX_RETRIES = 3;
export const TELEMETRY_RETRY_BASE_DELAY_MS = 500;

export type TelemetryEnvelope = {
  eventId: string;
  timestamp: string;
  sessionId: string;
  userId: string | null;
  event_type: string;
  schemaVersion: string;
  requestId: string;
  properties: Record<string, unknown>;
};

const queue: TelemetryEnvelope[] = [];
let flushing = false;
let started = false;
let nextRequestId: string | null = null;
let missingEndpointWarned = false;

const getTelemetryEndpoint = (): string | null => {
  const configured = process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
  if (!configured) {
    return null;
  }
  return configured.replace(/\/$/, "");
};

const pickAllowlistedProperties = (
  eventType: TelemetryEventType,
  properties: Record<string, unknown>,
): Record<string, unknown> | null => {
  const allowlist = EVENT_PROPERTY_ALLOWLIST[eventType];
  const required = EVENT_REQUIRED_PROPERTIES[eventType];
  const picked: Record<string, unknown> = {};

  for (const key of allowlist) {
    if (properties[key] !== undefined) {
      picked[key] = properties[key];
    }
  }

  for (const key of required) {
    if (picked[key] === undefined || picked[key] === null) {
      return null;
    }
  }

  return picked;
};

const wait = (delayMs: number): Promise<void> =>
  new Promise((resolve) => {
    window.setTimeout(resolve, delayMs);
  });

const postBatch = async (
  endpoint: string,
  events: TelemetryEnvelope[],
): Promise<boolean> => {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ events }),
  });
  return response.ok;
};

/**
 * Ordinary delivery: one attempt plus up to three retries with exponential
 * wait (500ms, 1s, 2s). After the final failure the batch is discarded so
 * telemetry cannot block inventory or auth work.
 */
const sendWithRetry = async (
  endpoint: string,
  events: TelemetryEnvelope[],
): Promise<void> => {
  const maxAttempts = TELEMETRY_MAX_RETRIES + 1;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const delivered = await postBatch(endpoint, events);
      if (delivered) {
        return;
      }
    } catch {
      // Network errors are retried; they must not surface to the UI.
    }
    if (attempt === maxAttempts) {
      return;
    }
    const delayMs = TELEMETRY_RETRY_BASE_DELAY_MS * 2 ** (attempt - 1);
    await wait(delayMs);
  }
};

const flushQueue = async (): Promise<void> => {
  if (flushing || queue.length === 0 || typeof window === "undefined") {
    return;
  }

  const endpoint = getTelemetryEndpoint();
  if (!endpoint) {
    if (!missingEndpointWarned) {
      missingEndpointWarned = true;
      console.warn(
        "NEXT_PUBLIC_TELEMETRY_ENDPOINT is not configured; telemetry batches are not sent.",
      );
    }
    return;
  }

  flushing = true;
  const batch = queue.splice(0, queue.length);
  if (batch.length === 0) {
    flushing = false;
    return;
  }
  try {
    await sendWithRetry(endpoint, batch);
  } finally {
    flushing = false;
  }
};

/**
 * Reserve the in-memory queue for a one-shot lifecycle send. Splice happens
 * before sendBeacon so visibilitychange and pagehide cannot both transmit
 * the same pending batch. If sendBeacon is missing, leave the queue in place.
 */
const flushWithBeacon = (): void => {
  if (typeof window === "undefined" || queue.length === 0) {
    return;
  }
  const endpoint = getTelemetryEndpoint();
  if (!endpoint || typeof navigator.sendBeacon !== "function") {
    return;
  }
  const batch = queue.splice(0, queue.length);
  if (batch.length === 0) {
    return;
  }
  const payload = JSON.stringify({ events: batch });
  let queued = false;
  try {
    // A JSON string is CORS-simple (text/plain) and remains readable as
    // request post data. Blob beacons can arrive with an empty postData.
    queued = navigator.sendBeacon(endpoint, payload);
  } catch {
    queued = false;
  }
  if (queued) {
    return;
  }
  try {
    const blob = new Blob([payload], { type: "text/plain" });
    queued = navigator.sendBeacon(endpoint, blob);
  } catch {
    queued = false;
  }
  if (queued) {
    return;
  }
  void fetch(endpoint, {
    method: "POST",
    body: payload,
    keepalive: true,
    mode: "cors",
    credentials: "omit",
    headers: { "Content-Type": "text/plain" },
  }).catch(() => {
    if (document.visibilityState !== "hidden") {
      queue.unshift(...batch);
    }
  });
};

const handleVisibilityChange = (): void => {
  if (document.visibilityState === "hidden") {
    flushWithBeacon();
  }
};

/**
 * Full navigation (location.assign, reload, close) does not wait for the
 * 10s interval. pagehide runs while the document can still send a beacon,
 * which is how session_expired survives the login redirect.
 */
const handlePageHide = (): void => {
  flushWithBeacon();
};

export const bindTelemetryRequestId = (requestId: string): void => {
  nextRequestId = requestId;
};

export const startTelemetry = (): void => {
  if (typeof window === "undefined" || started) {
    return;
  }
  started = true;
  getOrCreateTelemetrySessionId();
  window.setInterval(() => {
    void flushQueue();
  }, TELEMETRY_FLUSH_INTERVAL_MS);
  document.addEventListener("visibilitychange", handleVisibilityChange);
  window.addEventListener("pagehide", handlePageHide, { capture: true });
  window.addEventListener("beforeunload", handlePageHide);
};

export const track = (
  eventType: string,
  properties: Record<string, unknown>,
): void => {
  if (typeof window === "undefined") {
    return;
  }
  if (!isTelemetryEventType(eventType)) {
    return;
  }

  const allowlisted = pickAllowlistedProperties(eventType, properties);
  if (allowlisted === null) {
    return;
  }

  const requestId = nextRequestId ?? window.crypto.randomUUID();
  nextRequestId = null;

  const envelope: TelemetryEnvelope = {
    eventId: window.crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    sessionId: getOrCreateTelemetrySessionId(),
    userId: getTelemetryUserId(),
    event_type: eventType,
    schemaVersion: TELEMETRY_SCHEMA_VERSION,
    requestId,
    properties: allowlisted,
  };

  queue.push(envelope);
  // session_expired is followed immediately by location.assign. Send while
  // the document is still active; pagehide remains the path for other
  // queued events during tab hide and unload.
  if (eventType === "session_expired") {
    flushWithBeacon();
    return;
  }
  if (queue.length >= TELEMETRY_MAX_BATCH_SIZE) {
    void flushQueue();
  }
};
