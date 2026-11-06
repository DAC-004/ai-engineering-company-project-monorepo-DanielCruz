"use client";

import { FormEvent, useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import { useCurrentUser } from "@/lib/auth/CurrentUserContext";
import {
  FINANCIAL_CLOSE_FIGURE_IDS,
  contributorLabel,
  decideFinancialClose,
  isNamedTomReviewer,
  lineLabel,
  listFinancialCloseDrafts,
  lookupFinancialCloseFigure,
  moneyText,
  queueFinancialClose,
  readFinancialCloseJob,
  type CloseDraft,
  type CloseFigure,
} from "@/lib/financialClose";

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

export const FinancialClosePanel = () => {
  const currentUser = useCurrentUser();
  const canReview = isNamedTomReviewer(currentUser);
  const [drafts, setDrafts] = useState<CloseDraft[]>([]);
  const [status, setStatus] = useState("Loading close drafts…");
  const [kind, setKind] = useState<"" | "ok" | "error">("");
  const [figure, setFigure] = useState<CloseFigure | null>(null);

  const load = async () => {
    const rows = await listFinancialCloseDrafts();
    setDrafts(rows);
    setStatus(`Showing ${rows.length} close draft(s).`);
    setKind("ok");
  };

  useEffect(() => {
    let cancelled = false;
    void listFinancialCloseDrafts()
      .then((rows) => {
        if (!cancelled) {
          setDrafts(rows);
          setStatus(`Showing ${rows.length} close draft(s).`);
          setKind("ok");
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setStatus(error instanceof ApiError ? error.message : "Unable to load close drafts.");
          setKind("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleQueue = async () => {
    try {
      const job = await queueFinancialClose();
      setStatus(`Queued close job ${job.job_id}.`);
      for (let attempt = 0; attempt < 20; attempt += 1) {
        const latest = await readFinancialCloseJob(job.job_id);
        if (latest.status === "success" || latest.status === "failure") {
          setStatus(`Close job ${latest.status}.`);
          break;
        }
        await sleep(500);
      }
      await load();
    } catch (error) {
      setStatus(error instanceof ApiError ? error.message : "Unable to queue the close.");
      setKind("error");
    }
  };

  const handleLookup = async (draft: CloseDraft, event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const figureId = String(new FormData(event.currentTarget).get("figure_id") || "");
    try {
      setFigure(await lookupFinancialCloseFigure(draft.draft_id, figureId));
    } catch (error) {
      setFigure(null);
      setStatus(error instanceof ApiError ? error.message : "Figure lookup failed.");
      setKind("error");
    }
  };

  const handleDecide = async (event: FormEvent<HTMLFormElement>, draft: CloseDraft) => {
    event.preventDefault();
    if (!canReview || !draft.approval_nonce) {
      return;
    }
    const data = new FormData(event.currentTarget);
    const decision = String(data.get("decision") || "approve") as "approve" | "reject";
    const comments = String(data.get("comments") || "");
    try {
      await decideFinancialClose({
        draft_id: draft.draft_id,
        version: draft.version,
        content_sha256: draft.content_sha256,
        approval_nonce: draft.approval_nonce,
        decision,
        comments: decision === "reject" ? comments : undefined,
      });
      await load();
    } catch (error) {
      setStatus(error instanceof ApiError ? error.message : "The review could not be applied.");
      setKind("error");
    }
  };

  return (
    <section className="home-panel">
      <p className="eyebrow">Monthly close</p>
      <h1>Financial close</h1>
      <p className="home-lede">
        Seven-section close with actual, budget, and incomplete labels. Tom Callahan reviews in
        revenue cycle. Source lookup shows contributing rows, source ids, and hashes.
      </p>
      <p className={kind === "error" ? "form-error" : "home-lede"}>{status}</p>
      {canReview ? (
        <button type="button" className="btn-primary" onClick={() => void handleQueue()}>
          Run this month&apos;s close
        </button>
      ) : (
        <p>Only Tom Callahan, signed in as revenue-cycle supervisor, can queue or decide this close.</p>
      )}
      {figure ? (
        <div>
          <p>
            Lookup {figure.figure_id}: {figure.value ?? "missing"} · {figure.amount_status ?? "status unknown"} ·{" "}
            {figure.formula}
          </p>
          <p>Hash {figure.hash ?? "not supplied"}.</p>
          <ul>
            {(figure.contributing_rows ?? []).map((row, index) => (
              <li key={`${figure.figure_id}-${index}`}>{contributorLabel(row, index)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <ul className="mt-6 space-y-6">
        {drafts.map((draft) => (
          <li key={draft.draft_id} className="rounded border border-slate-200 p-4">
            <p>
              Period {draft.period} · version {draft.version} · {draft.state}
              {draft.incomplete ? " · incomplete" : ""}
            </p>
            <h2>1. Executive summary</h2>
            <p>{draft.executive_summary}</p>
            {draft.reviewer_guidance ? (
              <p>Reviewer comments on this revision: {draft.reviewer_guidance}</p>
            ) : null}
            <h2>2. Consolidated USD</h2>
            <p>
              Revenue budget {moneyText(draft.consolidated_usd?.revenue_budget_usd)} · revenue actual{" "}
              {moneyText(draft.consolidated_usd?.known_revenue_actual_usd, "incomplete")}
              {draft.consolidated_usd?.known_actuals_are_subtotals ? " (known subtotal, incomplete)" : ""}
            </p>
            <p>
              Expense budget {moneyText(draft.consolidated_usd?.expense_budget_usd)} · expense actual{" "}
              {moneyText(draft.consolidated_usd?.known_expense_actual_usd, "incomplete")}
              {draft.consolidated_usd?.known_actuals_are_subtotals ? " (known subtotal, incomplete)" : ""}
            </p>
            <p>
              Net budget {moneyText(draft.consolidated_usd?.result_budget_usd, "unavailable")} · net actual{" "}
              {moneyText(draft.consolidated_usd?.result_actual_usd, "incomplete")} · budget{" "}
              {String(draft.consolidated_usd?.budget_status ?? "incomplete")} · actual{" "}
              {String(draft.consolidated_usd?.actual_status ?? "incomplete")}
            </p>
            <h2>3. Revenue by country and payer</h2>
            <ul>
              {(draft.revenue_by_country_payer ?? []).map((row) => (
                <li key={String(row.line_id)}>{lineLabel(row)}</li>
              ))}
            </ul>
            <h2>4. Expenses by country</h2>
            <ul>
              {(draft.expenses_by_country ?? []).map((row) => (
                <li key={String(row.line_id)}>{lineLabel(row)}</li>
              ))}
            </ul>
            <h2>5. Relevant deviations</h2>
            <ul>
              {(draft.relevant_deviations ?? []).map((row) => (
                <li key={String(row.line_id)}>
                  {String(row.line_id)}: {String(row.hypothesis)}
                </li>
              ))}
            </ul>
            <h2>6. Missing or uncertain</h2>
            <ul>
              {(draft.missing_or_uncertain ?? []).map((row, index) => (
                <li key={`${String(row.reason)}-${index}`}>
                  {String(row.reason)}
                  {row.line_id ? ` · ${String(row.line_id)}` : ""}
                  {row.entry_id ? ` · ${String(row.entry_id)}` : ""}
                </li>
              ))}
            </ul>
            <h2>7. Traceability</h2>
            <p>
              FX {draft.fx_rate}. Load date {draft.load_date}. Digest {draft.facts_digest}.
            </p>
            <ul>
              {Object.entries(
                (draft.traceability?.file_hashes as Record<string, string> | undefined) ?? {},
              ).map(([name, hash]) => (
                <li key={name}>
                  {name}: {hash}
                </li>
              ))}
            </ul>
            <form onSubmit={(event) => void handleLookup(draft, event)}>
              <label>
                Source figure
                <select name="figure_id" defaultValue="us_laboratory.unit_price">
                  {(draft.figure_ids?.length ? draft.figure_ids : FINANCIAL_CLOSE_FIGURE_IDS).map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" className="btn-secondary">
                Look up source
              </button>
            </form>
            {canReview && draft.state === "awaiting_tom" && draft.approval_nonce ? (
              <form onSubmit={(event) => void handleDecide(event, draft)}>
                <label>
                  Decision
                  <select name="decision" defaultValue="approve">
                    <option value="approve">Approve</option>
                    <option value="reject">Reject</option>
                  </select>
                </label>
                <label>
                  Comments
                  <input name="comments" type="text" maxLength={4000} />
                </label>
                <button type="submit" className="btn-secondary">
                  Submit review
                </button>
              </form>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
};
