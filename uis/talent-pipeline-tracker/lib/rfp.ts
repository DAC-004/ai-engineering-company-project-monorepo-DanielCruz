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
  approval_status: string | null;
  approver: string | null;
  approved_at: string | null;
  submitted_by_user_id: string | null;
  approval_revision_count: number;
  iteration_limit_reached: boolean;
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
  rfp_id: string | null;
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
  part3_handoff: { response_complete?: boolean; currency?: string | null } | null;
  node_trace: Array<Record<string, unknown>> | null;
  arbitration_state: {
    phi_detected?: boolean;
    baa_dpa_mismatch?: boolean;
    baa_targets?: string[];
    open_questions?: string[];
    capacity?: {
      resolved?: boolean;
      population?: { count?: number; unit?: string; source_text?: string };
      coverage?: { count?: number; unit?: string; source_text?: string };
      resolution?: string | null;
    } | null;
  } | null;
};

export type RfpFinalDocument = {
  ticket_id: string;
  sections: Array<{ department_id: string; draft_content: string }>;
  currency: string | null;
  generated_at: string;
};

export type ApprovalDecisionName = "approve" | "reject" | "request_changes";

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

export const startRfpApproval = async (ticketId: string): Promise<RfpTicketCreated> => {
  return apiFetch<RfpTicketCreated>(`/rfp/tickets/${ticketId}/approval`, {
    method: "POST",
    auth: true,
  });
};

export const submitRfpDecision = async (
  ticketId: string,
  departmentId: string,
  body: { decision?: ApprovalDecisionName; note?: string; resolution?: "reduce_covered_population" | "add_sites" },
): Promise<RfpTicket> => {
  return apiFetch<RfpTicket>(`/rfp/tickets/${ticketId}/approval/${departmentId}`, {
    method: "POST",
    auth: true,
    body: JSON.stringify(body),
  });
};

export const getRfpFinalDocument = async (ticketId: string): Promise<RfpFinalDocument> => {
  return apiFetch<RfpFinalDocument>(`/rfp/tickets/${ticketId}/final-document`, {
    method: "GET",
    auth: true,
  });
};
