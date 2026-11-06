import { apiFetch } from "@/lib/auth/api";

export type SupplierContractRecord = {
  supplier_id: string;
  display_name: string;
  country: string;
  directory_country: string;
  category: string;
  quote_only: boolean;
  has_contract: boolean;
};

export type SupplierContractAlert = {
  id: string;
  kind: string;
  recipient: string;
  supplier_id: string;
  visibility_department?: string;
};

export type SupplierContractDraft = {
  draft_id: string;
  supplier_id: string;
  kind: string;
  body: string;
  version: number;
  content_sha256: string;
  approval_nonce: string;
  required: string[];
  granted: string[];
  state: string;
  sent: boolean;
  display_name?: string;
};

export type SupplierContractAskPayload = {
  answer?: string;
  blocked?: boolean;
  block_reason?: string | null;
  required_approvers?: string[];
  citations?: string[];
  alerts?: SupplierContractAlert[];
  draft?: SupplierContractDraft | null;
};

export const listContractSuppliers = async (): Promise<SupplierContractRecord[]> =>
  apiFetch<SupplierContractRecord[]>("/supplier-contracts/registry", {
    method: "GET",
    auth: true,
  });

export const listContractAlerts = async (): Promise<SupplierContractAlert[]> =>
  apiFetch<SupplierContractAlert[]>("/supplier-contracts/alerts", {
    method: "GET",
    auth: true,
  });

export const listContractDrafts = async (): Promise<SupplierContractDraft[]> =>
  apiFetch<SupplierContractDraft[]>("/supplier-contracts/drafts", {
    method: "GET",
    auth: true,
  });

export const getContractDraft = async (draftId: string): Promise<SupplierContractDraft> =>
  apiFetch<SupplierContractDraft>(`/supplier-contracts/drafts/${encodeURIComponent(draftId)}`, {
    method: "GET",
    auth: true,
  });

const QUESTION_KIND: Record<string, string> = {
  "Write a communication to the supplier.": "draft_communication",
  "Write a renegotiation brief with notice, exit, and sources.": "brief",
};

export const askSupplierContract = async (input: {
  question: string;
  supplier_id: string;
  kind?: string;
}): Promise<{ payload: SupplierContractAskPayload }> =>
  apiFetch<{ payload: SupplierContractAskPayload }>("/supplier-contracts/ask", {
    method: "POST",
    auth: true,
    body: JSON.stringify({
      kind: input.kind ?? QUESTION_KIND[input.question] ?? "question",
      question: input.question,
      supplier_id: input.supplier_id,
    }),
  });

export const approveSupplierContractDraft = async (draft: SupplierContractDraft): Promise<SupplierContractDraft> =>
  apiFetch<SupplierContractDraft>("/supplier-contracts/approvals", {
    method: "POST",
    auth: true,
    body: JSON.stringify({
      draft_id: draft.draft_id,
      version: draft.version,
      content_sha256: draft.content_sha256,
      approval_nonce: draft.approval_nonce,
    }),
  });

export const confirmSupplierContractDpa = async (supplier_id: string): Promise<Record<string, string>> =>
  apiFetch<Record<string, string>>("/supplier-contracts/dpa-proceed", {
    method: "POST",
    auth: true,
    body: JSON.stringify({ supplier_id }),
  });
