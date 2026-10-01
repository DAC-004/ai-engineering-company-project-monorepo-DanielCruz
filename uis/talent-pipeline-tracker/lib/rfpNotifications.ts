import { getAccessToken } from "@/lib/auth/token";

/**
 * One SSE connection for the authenticated workspace.
 * fetch keeps the bearer token. EventSource cannot send that header.
 * apiFetch reads response.json(), so it cannot consume this stream.
 */

export type RfpArrival = {
  ticketId: string;
  rfpId: string;
  status: string;
  createdAt: string;
};

const BACKOFF_MS = [1000, 2000, 4000, 8000, 16000, 30000];
const KEEPALIVE_INTERVAL_MS = 15000;

export const backoffDelayMs = (failureStep: number): number =>
  BACKOFF_MS[Math.min(Math.max(failureStep, 0), BACKOFF_MS.length - 1)];

const apiBaseUrl = (): string => {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }
  return baseUrl.replace(/\/$/, "");
};

type ParsedRecord = {
  id: string | null;
  eventName: string | null;
  data: string | null;
  comment: string | null;
};

export const parseSseBlock = (block: string): ParsedRecord => {
  let id: string | null = null;
  let eventName: string | null = null;
  let data: string | null = null;
  let comment: string | null = null;
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) {
      comment = line.slice(1).trim();
      continue;
    }
    if (line.startsWith("id:")) {
      id = line.slice(3).trim();
    } else if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      data = line.slice(5).trim();
    }
  }
  return { id, eventName, data, comment };
};

export const readArrival = (record: ParsedRecord): RfpArrival | null => {
  if (record.eventName !== "rfp_ticket_created" || !record.data) {
    return null;
  }
  const payload = JSON.parse(record.data) as {
    ticket_id?: string;
    rfp_id?: string;
    status?: string;
    created_at?: string;
  };
  if (!payload.ticket_id || !payload.rfp_id || !payload.status || !payload.created_at) {
    return null;
  }
  return {
    ticketId: payload.ticket_id,
    rfpId: payload.rfp_id,
    status: payload.status,
    createdAt: payload.created_at,
  };
};

type StreamHandlers = {
  onArrival: (arrival: RfpArrival) => void;
  onReplayGap: () => void;
  onEstablished: () => void;
  onEventId: (eventId: string) => void;
};

const consumeStream = async (
  response: Response,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> => {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("The RFP stream has no body.");
  }
  const decoder = new TextDecoder();
  let pending = "";
  while (!signal.aborted) {
    const chunk = await reader.read();
    if (chunk.done) {
      return;
    }
    pending += decoder.decode(chunk.value, { stream: true });
    const blocks = pending.split("\n\n");
    pending = blocks.pop() ?? "";
    for (const block of blocks) {
      if (!block.trim()) {
        continue;
      }
      const record = parseSseBlock(block);
      if (record.id) {
        handlers.onEventId(record.id);
      }
      if (record.comment === "keepalive") {
        handlers.onEstablished();
        continue;
      }
      if (record.comment === "replay-gap") {
        handlers.onReplayGap();
        continue;
      }
      const arrival = readArrival(record);
      if (arrival) {
        handlers.onEstablished();
        handlers.onArrival(arrival);
      }
    }
  }
};

/**
 * Reconnect until stop() is called.
 * An open that dies before a keepalive, an event, or one keepalive interval
 * advances the backoff. It does not return the wait to 1s.
 * That reset happens only after an established connection later fails.
 */
export const connectRfpNotifications = (
  handlers: StreamHandlers & { onConnectionError?: () => void },
): { stop: () => void } => {
  let stopped = false;
  let failureStep = 0;
  let lastEventId: string | null = null;
  let activeController: AbortController | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const schedule = (delayMs: number) => {
    if (stopped) {
      return;
    }
    reconnectTimer = setTimeout(() => {
      void open();
    }, delayMs);
  };

  const open = async () => {
    if (stopped) {
      return;
    }
    const token = getAccessToken();
    if (!token) {
      schedule(backoffDelayMs(failureStep));
      failureStep = Math.min(failureStep + 1, BACKOFF_MS.length - 1);
      return;
    }
    const controller = new AbortController();
    activeController = controller;
    let established = false;
    const markEstablished = () => {
      established = true;
    };
    const establishedTimer = setTimeout(markEstablished, KEEPALIVE_INTERVAL_MS);
    try {
      const headers: Record<string, string> = {
        Authorization: `Bearer ${token}`,
        Accept: "text/event-stream",
      };
      if (lastEventId) {
        headers["Last-Event-ID"] = lastEventId;
      }
      const response = await fetch(`${apiBaseUrl()}/rfp/tickets/stream`, {
        method: "GET",
        headers,
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`RFP stream failed with status ${response.status}`);
      }
      await consumeStream(
        response,
        {
          onArrival: (arrival) => {
            markEstablished();
            handlers.onArrival(arrival);
          },
          onReplayGap: handlers.onReplayGap,
          onEstablished: markEstablished,
          onEventId: (eventId) => {
            lastEventId = eventId;
          },
        },
        controller.signal,
      );
    } catch {
      if (stopped || controller.signal.aborted) {
        return;
      }
      handlers.onConnectionError?.();
    } finally {
      clearTimeout(establishedTimer);
    }
    if (stopped || controller.signal.aborted) {
      return;
    }
    if (established) {
      failureStep = 0;
      schedule(backoffDelayMs(0));
      failureStep = 1;
      return;
    }
    schedule(backoffDelayMs(failureStep));
    failureStep = Math.min(failureStep + 1, BACKOFF_MS.length - 1);
  };

  void open();

  return {
    stop: () => {
      stopped = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      activeController?.abort();
    },
  };
};
