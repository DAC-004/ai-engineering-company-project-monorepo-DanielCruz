import { apiFetch } from "@/lib/auth/api";

/**
 * RFP intake client. Uploads use FormData, so json stays false and the
 * browser sets the multipart boundary.
 */

export type RfpTicketCreated = {
  ticket_id: string;
  status: string;
};

export type RfpEvaluationResult = {
  overall_pass?: boolean;
  contains_phi?: boolean;
  feedback_for_generator?: string;
};

export type RfpDepartmentSection = {
  department_id: string;
  department_name: string | null;
  contact_name: string | null;
  key_aspects: {
    aspects: string[];
    open_questions: string[];
  };
  draft_content: string | null;
  evaluation_results: RfpEvaluationResult | null;
  needs_human_review: boolean;
};

export type RfpMetadata = {
  client_name: string | null;
  client_country: string | null;
  program_type: string | null;
  covered_population: string | null;
  deadline: string | null;
  budget_range: string | null;
  departments_needed: string[];
  flesch_kincaid_grade: number | null;
  gunning_fog: number | null;
};

export type RfpTicket = {
  ticket_id: string;
  status: string;
  raw_pdf_path: string | null;
  created_at: string;
  updated_at: string;
  processing_failed: boolean;
  processing_error_code: string | null;
  stalled: boolean;
  phi_detected: boolean;
  compliance_review_required: boolean;
  metadata: RfpMetadata | null;
  sections: RfpDepartmentSection[];
  synthesizer_summary: string | null;
  part2_handoff: Record<string, unknown> | null;
  part3_handoff: { response_complete?: boolean } | null;
};

export const createRfpTicket = async (file: File): Promise<RfpTicketCreated> => {
  const body = new FormData();
  body.append("file", file);
  return apiFetch<RfpTicketCreated>("/rfp/tickets", {
    method: "POST",
    auth: true,
    json: false,
    body,
  });
};

export const getRfpTicket = async (ticketId: string): Promise<RfpTicket> => {
  return apiFetch<RfpTicket>(`/rfp/tickets/${ticketId}`, {
    method: "GET",
    auth: true,
  });
};

export const startRfpResponse = async (ticketId: string): Promise<RfpTicketCreated> => {
  return apiFetch<RfpTicketCreated>(`/rfp/tickets/${ticketId}/response`, {
    method: "POST",
    auth: true,
  });
};
