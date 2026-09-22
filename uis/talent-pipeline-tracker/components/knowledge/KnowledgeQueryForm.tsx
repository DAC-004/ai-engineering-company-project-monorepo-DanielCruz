"use client";

import { FormEvent, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import { queryKnowledge } from "@/lib/knowledge";

type QueryStatus = "idle" | "loading" | "success" | "error";

export const KnowledgeQueryForm = () => {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [status, setStatus] = useState<QueryStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      setStatus("error");
      setAnswer(null);
      setErrorMessage("Enter a question before submitting.");
      return;
    }

    setStatus("loading");
    setErrorMessage(null);
    setAnswer(null);

    try {
      const generatedAnswer = await queryKnowledge(trimmedQuestion);
      setAnswer(generatedAnswer);
      setStatus("success");
    } catch (error) {
      setAnswer(null);
      setStatus("error");
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
        return;
      }
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "The knowledge assistant could not be reached.",
      );
    }
  };

  return (
    <form className="knowledge-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="knowledge-question">Coordinator question</label>
        <textarea
          id="knowledge-question"
          name="question"
          rows={4}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Example: Is there a charge for cancelling 12 hours in advance?"
          disabled={status === "loading"}
        />
      </div>
      <button type="submit" className="btn-primary" disabled={status === "loading"}>
        {status === "loading" ? "Searching approved policies…" : "Ask HealthCore knowledge"}
      </button>

      {status === "loading" ? (
        <p className="knowledge-status knowledge-status--loading" role="status">
          Retrieving approved HealthCore sources and drafting an answer…
        </p>
      ) : null}

      {status === "error" && errorMessage ? (
        <p className="form-error" role="alert">
          {errorMessage}
        </p>
      ) : null}

      {status === "success" && answer ? (
        <section className="knowledge-answer" aria-live="polite">
          <p className="eyebrow">Generated answer</p>
          <p>{answer}</p>
        </section>
      ) : null}
    </form>
  );
};
