import { apiFetch } from "@/lib/auth/api";

export type KnowledgeQueryResponse = {
  answer: string;
};

export const queryKnowledge = async (question: string): Promise<string> => {
  const response = await apiFetch<KnowledgeQueryResponse>("/knowledge/query", {
    method: "POST",
    body: JSON.stringify({ question }),
  });

  if (typeof response?.answer !== "string") {
    throw new Error("The knowledge endpoint did not return an answer string.");
  }

  return response.answer;
};
