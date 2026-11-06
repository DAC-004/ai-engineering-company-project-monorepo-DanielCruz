"use client";

import { FormEvent, useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import {
  askOnboardingQuestion,
  getMyOnboarding,
  requestOnboardingAccess,
  submitCheck,
  waitForOnboardingJob,
  type OnboardingSummary,
} from "@/lib/onboarding";

export const HireProgressPanel = () => {
  const [record, setRecord] = useState<OnboardingSummary | null>(null);
  const [status, setStatus] = useState("Loading your onboarding…");
  const [answers, setAnswers] = useState<number[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const refresh = async () => {
      try {
        const mine = await getMyOnboarding();
        if (cancelled) {
          return;
        }
        setRecord(mine);
        setAnswers((mine.questions ?? []).map(() => 0));
        setStatus(
          `Stage ${mine.current_stage} ${mine.stage_name}. Remaining: ${mine.pending_kind || "complete"}.`,
        );
        setError("");
      } catch (caught) {
        if (cancelled) {
          return;
        }
        setRecord(null);
        const message = caught instanceof ApiError ? caught.message : "Unable to load onboarding.";
        setStatus(message);
        setError(message);
      }
    };

    void refresh();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const onCheck = async (event: FormEvent) => {
    event.preventDefault();
    if (pending) {
      return;
    }
    if (!record?.decision_nonce) {
      setError("Missing decision nonce. Reloading your onboarding.");
      setReloadKey((current) => current + 1);
      return;
    }
    setPending(true);
    try {
      const accepted = await submitCheck(record.onboarding_id, {
        answers,
        decision_nonce: record.decision_nonce,
      });
      await waitForOnboardingJob(accepted.task_id);
      setReloadKey((current) => current + 1);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Check submission failed.");
    } finally {
      setPending(false);
    }
  };

  const onAsk = async (event: FormEvent) => {
    event.preventDefault();
    if (!record) return;
    try {
      const result = (await askOnboardingQuestion(record.onboarding_id, question)) as {
        answer: string;
        source_document?: string;
        covered?: boolean;
        route_to?: string | null;
      };
      const routed = result.route_to ? ` Routed to ${result.route_to}.` : "";
      setAnswer(
        result.source_document
          ? `${result.answer} (source: ${result.source_document})${routed}`
          : `${result.answer}${routed}`,
      );
      setError("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Question could not be submitted.");
    }
  };

  const onAccess = async (systemId: string) => {
    if (!record) return;
    try {
      await requestOnboardingAccess(record.onboarding_id, systemId);
      setReloadKey((current) => current + 1);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Access request failed.");
    }
  };

  return (
    <section className="home-panel">
      <p className="eyebrow">New hire</p>
      <h1>Your onboarding</h1>
      <p className="home-lede">{status}</p>
      {error ? <p role="alert">{error}</p> : null}
      {record?.last_rejection_comment ? <p>Last rejection: {record.last_rejection_comment}</p> : null}
      {record?.content ? (
        <article className="onboarding-official-content">
          <h2>{record.content.document_id}</h2>
          <pre className="onboarding-official-body">{record.content.body}</pre>
        </article>
      ) : null}
      {record?.questions ? (
        <form onSubmit={onCheck}>
          {record.questions.map((item, index) => (
            <fieldset key={item.id}>
              <legend>{item.prompt}</legend>
              {item.choices.map((choice, choiceIndex) => (
                <label key={choice}>
                  <input
                    type="radio"
                    name={item.id}
                    checked={answers[index] === choiceIndex}
                    disabled={pending}
                    onChange={() => {
                      const next = [...answers];
                      next[index] = choiceIndex;
                      setAnswers(next);
                    }}
                  />
                  {choice}
                </label>
              ))}
            </fieldset>
          ))}
          <button type="submit" className="btn-primary" disabled={pending}>
            {pending ? "Waiting for worker…" : "Submit check"}
          </button>
        </form>
      ) : null}
      {record ? (
        <form onSubmit={onAsk}>
          <label>
            Question
            <input value={question} onChange={(change) => setQuestion(change.target.value)} />
          </label>
          <button type="submit" className="btn-secondary">
            Ask from official material
          </button>
        </form>
      ) : null}
      {answer ? <p>{answer}</p> : null}
      {record ? (
        <>
          <button type="button" className="btn-secondary" onClick={() => void onAccess("jira")}>
            Request Jira access
          </button>
          <button type="button" className="btn-secondary" onClick={() => void onAccess("us_ehr")}>
            Request US EHR access
          </button>
        </>
      ) : null}
    </section>
  );
};
