"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchCurrentUser } from "@/lib/auth/session";
import { ApiError } from "@/lib/auth/types";
import {
  getRfpFinalDocument,
  getRfpTicket,
  startRfpApproval,
  startRfpResponse,
  submitRfpDecision,
  type ApprovalDecisionName,
  type RfpFinalDocument,
  type RfpTicket,
} from "@/lib/rfp";

const readabilityReason = (ticket: RfpTicket): string | null => {
  const handoff = ticket.part2_handoff;
  if (!handoff || typeof handoff !== "object") {
    return null;
  }
  const readability = handoff.readability;
  if (!readability || typeof readability !== "object") {
    return null;
  }
  const reason = (readability as { unavailable_reason?: unknown }).unavailable_reason;
  return typeof reason === "string" && reason.trim() ? reason : null;
};

const responseComplete = (ticket: RfpTicket): boolean => {
  return ticket.part3_handoff?.response_complete === true;
};

const readyToStartApproval = (ticket: RfpTicket): boolean => {
  return (
    responseComplete(ticket) &&
    (ticket.status === "under_evaluation" || ticket.status === "needs_human_review")
  );
};

const shouldPoll = (ticket: RfpTicket, watchGeneration: boolean): boolean => {
  if (ticket.processing_failed || ticket.status === "discarded" || ticket.status === "done") {
    return false;
  }
  if (ticket.status === "intake_complete") {
    return watchGeneration;
  }
  if (ticket.status === "waiting_for_approval") {
    return true;
  }
  if (readyToStartApproval(ticket)) {
    return false;
  }
  return true;
};

type RfpTicketPanelProps = {
  ticketId: string;
};

export const RfpTicketPanel = ({ ticketId }: RfpTicketPanelProps) => {
  const [ticket, setTicket] = useState<RfpTicket | null>(null);
  const [finalDocument, setFinalDocument] = useState<RfpFinalDocument | null>(null);
  const [signedInEmail, setSignedInEmail] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [watchGeneration, setWatchGeneration] = useState(false);
  const [actionInFlight, setActionInFlight] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    void fetchCurrentUser()
      .then((user) => {
        if (!cancelled) {
          setSignedInEmail(user.email);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSignedInEmail(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    const load = async () => {
      try {
        const nextTicket = await getRfpTicket(ticketId);
        if (cancelled) {
          return;
        }
        setTicket(nextTicket);
        setLoadError(null);
        if (nextTicket.status === "done") {
          const document = await getRfpFinalDocument(ticketId);
          if (!cancelled) {
            setFinalDocument(document);
          }
        }
        if (shouldPoll(nextTicket, watchGeneration)) {
          timer = window.setTimeout(() => {
            void load();
          }, 2000);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message = error instanceof ApiError ? error.message : "The ticket could not be loaded.";
        setLoadError(message);
      }
    };

    void load();
    return () => {
      cancelled = true;
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };
  }, [ticketId, watchGeneration, actionInFlight]);

  const handleGenerate = async () => {
    setGenerationError(null);
    try {
      await startRfpResponse(ticketId);
      setWatchGeneration(true);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Proposal generation could not be started.";
      setGenerationError(message);
    }
  };

  const handleStartApproval = async () => {
    setApprovalError(null);
    setActionInFlight("start");
    try {
      await startRfpApproval(ticketId);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Approval could not be started.";
      setApprovalError(message);
    } finally {
      setActionInFlight(null);
    }
  };

  const handleDecision = async (departmentId: string, decision: ApprovalDecisionName) => {
    const note = notes[departmentId] ?? "";
    if ((decision === "reject" || decision === "request_changes") && !note.trim()) {
      setApprovalError("A note is required to reject or request changes.");
      return;
    }
    setApprovalError(null);
    setActionInFlight(departmentId);
    try {
      const nextTicket = await submitRfpDecision(ticketId, departmentId, {
        decision,
        note: note.trim() || undefined,
      });
      setTicket(nextTicket);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "The decision was not accepted.";
      setApprovalError(message);
    } finally {
      setActionInFlight(null);
    }
  };

  const handleResolution = async (resolution: "reduce_covered_population" | "add_sites") => {
    setApprovalError(null);
    setActionInFlight("capacity");
    try {
      const nextTicket = await submitRfpDecision(ticketId, "revenue", { resolution });
      setTicket(nextTicket);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "The capacity choice was not accepted.";
      setApprovalError(message);
    } finally {
      setActionInFlight(null);
    }
  };

  if (loadError) {
    return <p className="form-error">{loadError}</p>;
  }
  if (!ticket) {
    return <p>Loading ticket.</p>;
  }

  const capacity = ticket.arbitration_state?.capacity;
  const capacityOpen = Boolean(capacity && capacity.resolved !== true);
  const regulatoryOpen = Boolean(
    ticket.arbitration_state?.phi_detected || ticket.arbitration_state?.baa_dpa_mismatch,
  );

  return (
    <div className="auth-form">
      <p>
        Status: <strong>{ticket.status}</strong>
      </p>
      <p>Signed in as: {signedInEmail ?? "Not available"}</p>
      {ticket.processing_failed ? (
        <p className="form-error">Processing failed. Code: {ticket.processing_error_code ?? "pipeline_exception"}</p>
      ) : null}
      {ticket.stalled ? (
        <p>This ticket is still analyzing and has not been updated recently.</p>
      ) : null}
      {ticket.status === "discarded" ? <p>This request was discarded. No department work was stored.</p> : null}
      {ticket.status === "intake_complete" && !responseComplete(ticket) ? (
        <p>
          <button type="button" onClick={() => void handleGenerate()} disabled={actionInFlight !== null}>
            Generate proposal sections
          </button>
        </p>
      ) : null}
      {generationError ? <p className="form-error">{generationError}</p> : null}
      {readyToStartApproval(ticket) ? (
        <p>
          <button type="button" onClick={() => void handleStartApproval()} disabled={actionInFlight !== null}>
            Start department approval
          </button>
        </p>
      ) : null}
      {approvalError ? <p className="form-error">{approvalError}</p> : null}
      {ticket.compliance_review_required ? (
        <p>Compliance review is required before this ticket can close.</p>
      ) : null}
      {ticket.arbitration_state?.open_questions && ticket.arbitration_state.open_questions.length > 0 ? (
        <section>
          <h2>Open questions</h2>
          <ul>
            {ticket.arbitration_state.open_questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {capacityOpen ? (
        <section>
          <h2>Capacity conflict</h2>
          <p>
            Population {capacity?.population?.count} {capacity?.population?.unit}. Coverage {capacity?.coverage?.count}{" "}
            {capacity?.coverage?.unit}. Tom Callahan chooses reduce covered population or add sites. This form does not
            accept a new number.
          </p>
          {regulatoryOpen ? <p>Compliance must clear PHI and the country clause before that choice.</p> : null}
          {!regulatoryOpen && ticket.status === "waiting_for_approval" ? (
            <p>
              <button
                type="button"
                onClick={() => void handleResolution("reduce_covered_population")}
                disabled={actionInFlight !== null}
              >
                Reduce covered population
              </button>{" "}
              <button type="button" onClick={() => void handleResolution("add_sites")} disabled={actionInFlight !== null}>
                Add sites
              </button>
            </p>
          ) : null}
        </section>
      ) : null}
      {ticket.metadata ? (
        <section>
          <h2>Request</h2>
          <ul>
            <li>Client: {ticket.metadata.client_name ?? "Not stated"}</li>
            <li>Country: {ticket.metadata.client_country ?? "Not stated"}</li>
            <li>Program: {ticket.metadata.program_type ?? "Not stated"}</li>
            <li>Covered population: {ticket.metadata.covered_population ?? "Not stated"}</li>
            <li>Deadline: {ticket.metadata.deadline ?? "Not stated"}</li>
            <li>Budget: {ticket.metadata.budget_range ?? "Not stated"}</li>
            <li>Flesch-Kincaid grade: {ticket.metadata.flesch_kincaid_grade ?? "Not scored"}</li>
            <li>Gunning fog: {ticket.metadata.gunning_fog ?? "Not scored"}</li>
            {readabilityReason(ticket) ? <li>Readability note: {readabilityReason(ticket)}</li> : null}
          </ul>
        </section>
      ) : null}
      {ticket.sections.map((section) => {
        const waiting = ticket.status === "waiting_for_approval" && section.approval_status !== "approved";
        const busy = actionInFlight !== null;
        return (
          <section key={section.department_id}>
            <h2>
              {section.department_name ?? section.department_id}
              {section.contact_name ? `, ${section.contact_name}` : ""}
            </h2>
            <p>Required approver: {section.contact_name ?? "Not assigned"}</p>
            <p>Approval status: {section.approval_status ?? "Not started"}</p>
            {section.approver ? <p>Recorded approver: {section.approver}</p> : null}
            {section.iteration_limit_reached ? (
              <p>The revision limit is reached. The current screened draft can still be approved when the checks pass.</p>
            ) : null}
            <h3>Key aspects</h3>
            <ul>
              {section.key_aspects.aspects.length > 0 ? (
                section.key_aspects.aspects.map((aspect) => <li key={aspect}>{aspect}</li>)
              ) : (
                <li>None recorded.</li>
              )}
            </ul>
            {section.needs_human_review ? (
              <p>Provisional draft. This section needs human review. The other departments still stay on this ticket.</p>
            ) : null}
            {section.draft_content ? (
              <>
                <h3>Draft</h3>
                <p>{section.draft_content}</p>
              </>
            ) : null}
            {section.evaluation_results ? (
              <>
                <h3>Evaluation</h3>
                <p>
                  {section.evaluation_results.overall_pass ? "Passed evaluation." : "Evaluation did not pass."}
                  {section.evaluation_results.feedback_for_generator
                    ? ` ${section.evaluation_results.feedback_for_generator}`
                    : ""}
                </p>
              </>
            ) : null}
            <h3>Open questions</h3>
            <ul>
              {section.key_aspects.open_questions.length > 0 ? (
                section.key_aspects.open_questions.map((question) => <li key={question}>{question}</li>)
              ) : (
                <li>None recorded.</li>
              )}
            </ul>
            {waiting ? (
              <>
                <label htmlFor={`note-${section.department_id}`}>
                  Note, required for reject or request changes
                  <textarea
                    id={`note-${section.department_id}`}
                    value={notes[section.department_id] ?? ""}
                    onChange={(event) =>
                      setNotes((current) => ({ ...current, [section.department_id]: event.target.value }))
                    }
                  />
                </label>
                <p>
                  <button type="button" onClick={() => void handleDecision(section.department_id, "approve")} disabled={busy}>
                    Approve
                  </button>{" "}
                  <button type="button" onClick={() => void handleDecision(section.department_id, "reject")} disabled={busy}>
                    Reject
                  </button>{" "}
                  <button
                    type="button"
                    onClick={() => void handleDecision(section.department_id, "request_changes")}
                    disabled={busy}
                  >
                    Request changes
                  </button>
                </p>
              </>
            ) : null}
          </section>
        );
      })}
      {ticket.synthesizer_summary ? (
        <section>
          <h2>Revenue Cycle summary</h2>
          <p>{ticket.synthesizer_summary}</p>
        </section>
      ) : null}
      {ticket.status === "done" && finalDocument ? (
        <section>
          <h2>Final document</h2>
          <p>Currency: {finalDocument.currency ?? "Not stated"}</p>
          <p>Generated at: {finalDocument.generated_at}</p>
          {finalDocument.sections.map((section) => (
            <article key={section.department_id}>
              <h3>{section.department_id}</h3>
              <p>{section.draft_content}</p>
            </article>
          ))}
        </section>
      ) : null}
      <p>
        <Link href="/backoffice/rfp">Upload another request</Link>
      </p>
    </div>
  );
};
