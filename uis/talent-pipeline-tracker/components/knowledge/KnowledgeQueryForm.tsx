"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { getAccessToken } from "@/lib/auth/token";
import {
  getOrCreateKnowledgeSessionId,
  knowledgeSocketUrl,
} from "@/lib/knowledge-chat";

type TranscriptMessage = {
  messageId: string;
  role: "user" | "assistant";
  text: string;
  interrupted: boolean;
  streaming: boolean;
};

type ChatEvent = {
  event?: unknown;
  data?: unknown;
};

const BACKOFF_START_MS = 500;
const BACKOFF_CAP_MS = 8000;

const readString = (value: unknown): string => (typeof value === "string" ? value : "");

const snapshotMessages = (value: unknown): TranscriptMessage[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item, index) => {
    if (typeof item !== "object" || item === null) {
      return [];
    }
    const record = item as { message_id?: unknown; role?: unknown; text?: unknown; status?: unknown };
    if (record.role !== "user" && record.role !== "assistant") {
      return [];
    }
    const messageId = readString(record.message_id) || `${record.role}-snapshot-${index}`;
    return [
      {
        messageId,
        role: record.role,
        text: readString(record.text),
        interrupted: record.role === "assistant" && record.status === "interrupted",
        streaming: false,
      },
    ];
  });
};

const appendToken = (current: TranscriptMessage[], token: string): TranscriptMessage[] => {
  const last = current.at(-1);
  if (last?.role === "assistant" && last.streaming) {
    return [...current.slice(0, -1), { ...last, text: last.text + token }];
  }
  return [
    ...current,
    {
      messageId: `streaming-${current.length}`,
      role: "assistant",
      text: token,
      interrupted: false,
      streaming: true,
    },
  ];
};

const finishAssistant = (
  current: TranscriptMessage[],
  messageId: string,
  interrupted: boolean,
): TranscriptMessage[] => {
  const last = current.at(-1);
  if (last?.role !== "assistant" || (!last.streaming && !interrupted)) {
    return current;
  }
  return [
    ...current.slice(0, -1),
    {
      ...last,
      messageId: messageId || last.messageId,
      interrupted,
      streaming: false,
    },
  ];
};

export const KnowledgeQueryForm = () => {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [connectionLabel, setConnectionLabel] = useState("Connecting…");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef("");
  const awaitingSnapshotRef = useRef(true);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const streamingRef = useRef(false);
  const userSequenceRef = useRef(0);

  useEffect(() => {
    streamingRef.current = streaming;
  }, [streaming]);

  useEffect(() => {
    let disposed = false;
    sessionIdRef.current = getOrCreateKnowledgeSessionId();

    let continueRestoredAssistant = false;

    const applyEvent = (payload: ChatEvent) => {
      const eventName = readString(payload.event);
      const data =
        typeof payload.data === "object" && payload.data !== null
          ? (payload.data as Record<string, unknown>)
          : {};

      if (awaitingSnapshotRef.current) {
        if (eventName !== "session_snapshot") {
          return;
        }
        const restored = snapshotMessages(data.messages);
        const last = restored.at(-1);
        continueRestoredAssistant = last?.role === "assistant" && !last.interrupted;
        setMessages(restored);
        awaitingSnapshotRef.current = false;
        reconnectAttemptRef.current = 0;
        setConnectionLabel("Connected");
        setErrorMessage(null);
        setStreaming(false);
        return;
      }

      if (eventName === "user_message") {
        const text = readString(data.text);
        if (!text) {
          return;
        }
        continueRestoredAssistant = false;
        userSequenceRef.current += 1;
        const messageId = `user-${userSequenceRef.current}`;
        setMessages((current) => [
          ...current,
          { messageId, role: "user", text, interrupted: false, streaming: false },
        ]);
        return;
      }

      if (eventName === "token_chunk") {
        const token = readString(data.token);
        if (!token) {
          return;
        }
        setStreaming(true);
        setMessages((current) => {
          const last = current.at(-1);
          if (
            last?.role === "assistant" &&
            !last.interrupted &&
            (last.streaming || continueRestoredAssistant)
          ) {
            continueRestoredAssistant = false;
            return [...current.slice(0, -1), { ...last, text: last.text + token, streaming: true }];
          }
          continueRestoredAssistant = false;
          return appendToken(current, token);
        });
        return;
      }

      if (eventName === "generation_completed") {
        setStreaming(false);
        setMessages((current) => finishAssistant(current, readString(data.message_id), false));
        return;
      }

      if (eventName === "generation_interrupted") {
        setStreaming(false);
        setMessages((current) => finishAssistant(current, readString(data.message_id), true));
      }
    };

    const connect = () => {
      if (disposed) {
        return;
      }
      const token = getAccessToken();
      if (!token) {
        setConnectionLabel("Sign-in required");
        setErrorMessage("The knowledge assistant needs a backoffice sign-in.");
        return;
      }
      awaitingSnapshotRef.current = true;
      let socket: WebSocket;
      try {
        socket = new WebSocket(knowledgeSocketUrl(sessionIdRef.current));
      } catch (error) {
        setConnectionLabel("Disconnected");
        setErrorMessage(error instanceof Error ? error.message : "The chat socket could not be opened.");
        return;
      }
      socketRef.current = socket;
      socket.onopen = () => {
        // The JWT stays in this frame. The handshake URL has no query string,
        // so the server access log cannot record the credential.
        socket.send(JSON.stringify({ event: "auth", data: { token } }));
      };
      socket.onmessage = (event) => {
        if (disposed || socketRef.current !== socket) {
          return;
        }
        try {
          applyEvent(JSON.parse(String(event.data)) as ChatEvent);
        } catch {
          setErrorMessage("The assistant sent a message that could not be read.");
        }
      };
      socket.onclose = (closeEvent) => {
        const wasCurrent = socketRef.current === socket;
        if (wasCurrent) {
          socketRef.current = null;
        }
        if (disposed || !wasCurrent) {
          return;
        }
        setStreaming(false);
        if (closeEvent.code === 1008) {
          setConnectionLabel("Rejected");
          setErrorMessage("The backoffice sign-in was rejected.");
          return;
        }
        const delay = Math.min(
          BACKOFF_CAP_MS,
          BACKOFF_START_MS * 2 ** reconnectAttemptRef.current,
        );
        reconnectAttemptRef.current += 1;
        setConnectionLabel(`Reconnecting in ${delay / 1000}s…`);
        reconnectTimerRef.current = window.setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      socketRef.current?.close();
    };
  }, []);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      setErrorMessage("Enter a question before submitting.");
      return;
    }
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN || awaitingSnapshotRef.current) {
      setErrorMessage("The assistant is not connected yet.");
      return;
    }
    const interrupting = streamingRef.current;
    socket.send(
      JSON.stringify(
        interrupting
          ? {
              event: "interrupt_requested",
              data: { session_id: sessionIdRef.current, new_input: trimmedQuestion },
            }
          : {
              event: "user_message",
              data: { session_id: sessionIdRef.current, text: trimmedQuestion },
            },
      ),
    );
    setQuestion("");
    setErrorMessage(null);
  };

  return (
    <form className="knowledge-form" onSubmit={handleSubmit}>
      <p className="knowledge-status" role="status">
        {connectionLabel}
      </p>
      <div className="field">
        <label htmlFor="knowledge-question">Coordinator question</label>
        <textarea
          id="knowledge-question"
          name="question"
          rows={4}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Example: Is there a charge for cancelling 12 hours in advance?"
        />
      </div>
      <button type="submit" className="btn-primary">
        {streaming ? "Interrupt and ask this instead" : "Ask HealthCore knowledge"}
      </button>

      {errorMessage ? (
        <p className="form-error" role="alert">
          {errorMessage}
        </p>
      ) : null}

      <ol className="knowledge-thread">
        {messages.map((message) => (
          <li
            key={message.messageId}
            className={
              message.interrupted
                ? "knowledge-message knowledge-message--interrupted"
                : "knowledge-message"
            }
          >
            <p className="eyebrow">{message.role === "user" ? "You" : "Assistant"}</p>
            {message.interrupted ? (
              <p className="knowledge-interrupted-mark">Interrupted</p>
            ) : null}
            <p aria-live={message.streaming ? "polite" : "off"}>{message.text}</p>
          </li>
        ))}
      </ol>
    </form>
  );
};
