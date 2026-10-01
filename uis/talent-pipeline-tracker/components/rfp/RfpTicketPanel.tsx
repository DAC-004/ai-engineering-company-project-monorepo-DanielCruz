"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ApiError } from "@/lib/auth/types";
import { getRfpTicket, startRfpResponse, type RfpTicket } from "@/lib/rfp";

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

const shouldPoll = (ticket: RfpTicket, watchGeneration: boolean): boolean => {
  if (ticket.processing_failed || ticket.status === "discarded" || responseComplete(ticket)) {
    return false;
  }
  if (ticket.status === "intake_complete") {
    return watchGeneration;
  }
  return true;
};

type RfpTicketPanelProps = {
  ticketId: string;
};

export const RfpTicketPanel = ({ ticketId }: RfpTicketPanelProps) => {
  const [ticket, setTicket] = useState<RfpTicket | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [watchGeneration, setWatchGeneration] = useState(false);

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
  }, [ticketId, watchGeneration]);

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

  if (loadError) {
    return <p className="form-error">{loadError}</p>;
  }
  if (!ticket) {
    return <p>Loading ticket.</p>;
  }

  return (
    <div className="auth-form">
      <p>
        Status: <strong>{ticket.status}</strong>
      </p>
      {ticket.processing_failed ? (
        <p className="form-error">Processing failed. Code: {ticket.processing_error_code ?? "pipeline_exception"}</p>
      ) : null}
      {ticket.stalled ? (
        <p>This ticket is still analyzing and has not been updated recently.</p>
      ) : null}
      {ticket.status === "discarded" ? <p>This request was discarded. No department work was stored.</p> : null}
      {ticket.status === "intake_complete" && !responseComplete(ticket) ? (
        <p>
          <button type="button" onClick={() => void handleGenerate()}>
            Generate proposal sections
          </button>
        </p>
      ) : null}
      {generationError ? <p className="form-error">{generationError}</p> : null}
      {responseComplete(ticket) && ticket.status === "under_evaluation" ? (
        <p>Evaluation is complete. This ticket is ready for Part 3 review.</p>
      ) : null}
      {ticket.compliance_review_required ? (
        <p>Compliance review is required before this ticket can continue.</p>
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
      {ticket.sections.map((section) => (
        <section key={section.department_id}>
          <h2>
            {section.department_name ?? section.department_id}
            {section.contact_name ? `, ${section.contact_name}` : ""}
          </h2>
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
        </section>
      ))}
      {ticket.synthesizer_summary ? (
        <section>
          <h2>Revenue Cycle summary</h2>
          <p>{ticket.synthesizer_summary}</p>
        </section>
      ) : null}
      <p>
        <Link href="/backoffice/rfp">Upload another request</Link>
      </p>
    </div>
  );
};
