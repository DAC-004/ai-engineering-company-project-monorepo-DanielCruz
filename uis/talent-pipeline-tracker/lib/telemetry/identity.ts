import { getAccessToken } from "@/lib/auth/token";

const SESSION_STORAGE_KEY = "healthcore.telemetry.sessionId";

type JwtPayload = {
  sub?: unknown;
  exp?: unknown;
};

/**
 * Read the JWT payload without verifying the signature.
 *
 * Envelope userId must be TinyDB `sub`, never email. Verification stays on
 * the API; this decode is only used to attach a non-PII identifier.
 */
export const readJwtPayload = (token: string): JwtPayload | null => {
  const segments = token.split(".");
  if (segments.length < 2) {
    return null;
  }
  try {
    const normalized = segments[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(
      normalized.length + ((4 - (normalized.length % 4)) % 4),
      "=",
    );
    return JSON.parse(window.atob(padded)) as JwtPayload;
  } catch {
    return null;
  }
};

export const getTelemetryUserId = (): string | null => {
  const token = getAccessToken();
  if (!token) {
    return null;
  }
  const payload = readJwtPayload(token);
  return typeof payload?.sub === "string" && payload.sub.length > 0
    ? payload.sub
    : null;
};

export const getJwtExpiryMs = (): number | null => {
  const token = getAccessToken();
  if (!token) {
    return null;
  }
  const payload = readJwtPayload(token);
  return typeof payload?.exp === "number" ? payload.exp * 1000 : null;
};

export const isJwtExpired = (nowMs: number = Date.now()): boolean => {
  const expiryMs = getJwtExpiryMs();
  if (expiryMs === null) {
    return false;
  }
  return expiryMs <= nowMs;
};

export const getOrCreateTelemetrySessionId = (): string => {
  if (typeof window === "undefined") {
    return "00000000-0000-4000-8000-000000000000";
  }
  const existing = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const sessionId = window.crypto.randomUUID();
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  return sessionId;
};
