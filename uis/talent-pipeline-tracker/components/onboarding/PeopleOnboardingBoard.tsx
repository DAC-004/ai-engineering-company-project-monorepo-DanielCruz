"use client";

import { FormEvent, useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import {
  getOnboarding,
  listOnboardings,
  submitDecision,
  submitPaperwork,
  waitForOnboardingJob,
  type OnboardingSummary,
} from "@/lib/onboarding";

const HUMAN_GATES = new Set(["compliance_approval", "manager_approval", "closure"]);

export const PeopleOnboardingBoard = () => {
  const [rows, setRows] = useState<OnboardingSummary[]>([]);
  const [status, setStatus] = useState("Loading onboardings…");
  const [error, setError] = useState("");
  const [commentById, setCommentById] = useState<Record<string, string>>({});
  const [paperworkById, setPaperworkById] = useState<
    Record<string, { documents_received: boolean; background_check_completed: boolean }>
  >({});
  const [reloadKey, setReloadKey] = useState(0);
  const [pendingId, setPendingId] = useState("");

  useEffect(() => {
    let cancelled = false;

    const refresh = async () => {
      try {
        const listed = await listOnboardings();
        const detailed = await Promise.all(listed.map((row) => getOnboarding(row.onboarding_id)));
        if (cancelled) {
          return;
        }
        setRows(detailed);
        setPaperworkById((current) => {
          const next = { ...current };
          for (const row of detailed) {
            if (!next[row.onboarding_id]) {
              next[row.onboarding_id] = {
                documents_received: Boolean(row.paperwork_received),
                background_check_completed: Boolean(row.background_check_completed),
              };
            }
          }
          return next;
        });
        setStatus(`Showing ${detailed.length} onboarding(s).`);
        setError("");
      } catch (caught) {
        if (cancelled) {
          return;
        }
        setRows([]);
        const message = caught instanceof ApiError ? caught.message : "Unable to load onboardings.";
        setStatus(message);
        setError(message);
      }
    };

    void refresh();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const onPaperwork = async (row: OnboardingSummary) => {
    if (pendingId) {
      return;
    }
    if (!row.decision_nonce) {
      setError("Missing decision nonce. Reloading details.");
      setReloadKey((current) => current + 1);
      return;
    }
    const flags = paperworkById[row.onboarding_id] ?? {
      documents_received: false,
      background_check_completed: false,
    };
    if (!flags.documents_received || !flags.background_check_completed) {
      setError("Confirm both paperwork received and background-check completion before recording.");
      return;
    }
    setPendingId(row.onboarding_id);
    try {
      const accepted = await submitPaperwork(row.onboarding_id, {
        documents_received: flags.documents_received,
        background_check_completed: flags.background_check_completed,
        decision_nonce: row.decision_nonce,
      });
      await waitForOnboardingJob(accepted.task_id);
      setReloadKey((current) => current + 1);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Paperwork update failed.");
    } finally {
      setPendingId("");
    }
  };

  const onDecide = async (row: OnboardingSummary, decision: "approve" | "reject") => {
    if (pendingId) {
      return;
    }
    if (!row.decision_nonce) {
      setError("Missing decision nonce. Reloading details.");
      setReloadKey((current) => current + 1);
      return;
    }
    setPendingId(row.onboarding_id);
    try {
      const accepted = await submitDecision(row.onboarding_id, {
        decision,
        comment: commentById[row.onboarding_id] ?? "",
        decision_nonce: row.decision_nonce,
      });
      await waitForOnboardingJob(accepted.task_id);
      setCommentById((current) => ({ ...current, [row.onboarding_id]: "" }));
      setReloadKey((current) => current + 1);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Decision failed.");
    } finally {
      setPendingId("");
    }
  };

  return (
    <section className="home-panel">
      <p className="eyebrow">People team</p>
      <h1>Corporate onboarding</h1>
      <p className="home-lede">{status}</p>
      {error ? <p role="alert">{error}</p> : null}
      <ul>
        {rows.map((row) => (
          <li key={row.onboarding_id}>
            <strong>{row.display_name}</strong> · stage {row.current_stage} {row.stage_name} ·{" "}
            {row.status}
            {row.blocked ? " · blocked" : ""}
            {row.pending_kind ? ` · pending ${row.pending_kind}` : ""}
            {row.last_rejection_comment ? <p>Last rejection: {row.last_rejection_comment}</p> : null}
            {row.pending_kind === "paperwork" ? (
              <form
                onSubmit={(event: FormEvent) => {
                  event.preventDefault();
                  void onPaperwork(row);
                }}
              >
                <label>
                  <input
                    type="checkbox"
                    disabled={Boolean(pendingId)}
                    checked={Boolean(paperworkById[row.onboarding_id]?.documents_received)}
                    onChange={(change) =>
                      setPaperworkById((current) => ({
                        ...current,
                        [row.onboarding_id]: {
                          documents_received: change.target.checked,
                          background_check_completed:
                            current[row.onboarding_id]?.background_check_completed ?? false,
                        },
                      }))
                    }
                  />
                  Documents received
                </label>
                <label>
                  <input
                    type="checkbox"
                    disabled={Boolean(pendingId)}
                    checked={Boolean(paperworkById[row.onboarding_id]?.background_check_completed)}
                    onChange={(change) =>
                      setPaperworkById((current) => ({
                        ...current,
                        [row.onboarding_id]: {
                          documents_received: current[row.onboarding_id]?.documents_received ?? false,
                          background_check_completed: change.target.checked,
                        },
                      }))
                    }
                  />
                  Background check completed
                </label>
                <button type="submit" className="btn-primary" disabled={Boolean(pendingId)}>
                  {pendingId === row.onboarding_id
                    ? "Waiting for worker…"
                    : "Record paperwork confirmation"}
                </button>
              </form>
            ) : null}
            {HUMAN_GATES.has(row.pending_kind) ? (
              <form
                onSubmit={(event: FormEvent) => {
                  event.preventDefault();
                  void onDecide(row, "approve");
                }}
              >
                <label>
                  Comment
                  <input
                    disabled={Boolean(pendingId)}
                    value={commentById[row.onboarding_id] ?? ""}
                    onChange={(change) =>
                      setCommentById((current) => ({
                        ...current,
                        [row.onboarding_id]: change.target.value,
                      }))
                    }
                  />
                </label>
                <button type="submit" className="btn-primary" disabled={Boolean(pendingId)}>
                  {pendingId === row.onboarding_id
                    ? "Waiting for worker…"
                    : `Approve ${row.pending_kind.replace("_", " ")}`}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={Boolean(pendingId)}
                  onClick={() => void onDecide(row, "reject")}
                >
                  Reject
                </button>
              </form>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
};
