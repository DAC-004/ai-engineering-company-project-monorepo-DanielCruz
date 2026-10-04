const SESSION_STORAGE_KEY = "healthcore.knowledge.session_id";
const SESSION_ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

const apiBaseUrl = (): string => {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }
  return baseUrl.replace(/\/$/, "");
};

export const getOrCreateKnowledgeSessionId = (): string => {
  const existing = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (existing && SESSION_ID_PATTERN.test(existing)) {
    return existing;
  }
  const created = `chat_${crypto.randomUUID().replace(/-/g, "").slice(0, 16)}`;
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, created);
  return created;
};

export const knowledgeSocketUrl = (sessionId: string): string => {
  const webSocketBase = apiBaseUrl().replace(/^http/i, "ws");
  return new URL(`${webSocketBase}/ws/chat/${sessionId}`).toString();
};
