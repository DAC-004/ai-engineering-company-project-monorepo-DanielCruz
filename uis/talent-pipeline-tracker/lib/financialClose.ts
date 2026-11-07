import { apiFetch } from "@/lib/auth/api";
import type { AuthMeResponse } from "@/lib/auth/types";

export const TOM_CLOSE_EMAIL = "tom.billing@healthcore.example";
export const TOM_CLOSE_ROLE = "supervisor";
export const TOM_CLOSE_DEPARTMENT = "revenue_cycle";

export const FINANCIAL_CLOSE_FIGURE_IDS = [
  "us_laboratory.verified_actual",
  "us_laboratory.budget",
  "us_laboratory.percent",
  "us_laboratory.unit_price",
  "us_laboratory.observed_quantity",
  "us_laboratory.budget_implied_unit_price",
  "us_laboratory.increase",
  "us_laboratory.amount_variance",
  "us_medicare_medicaid_revenue.amount_variance",
  "us_medicare_medicaid_revenue.verified_actual",
  "consolidated.result_budget_usd",
  "fx.rate",
  "operations.medicare.claims_submitted_actual",
  "operations.medicare.claims_submitted_budget",
  "operations.medicare.denial_rate_pct_actual",
  "operations.medicare.denial_rate_pct_budget",
  "operations.commercial.claims_submitted_actual",
  "operations.commercial.claims_submitted_budget",
  "operations.commercial.denial_rate_pct_actual",
  "operations.commercial.denial_rate_pct_budget",
] as const;

export type CloseMoneyRow = {
  line_id?: string;
  category?: string | null;
  country?: string | null;
  payer?: string | null;
  currency?: string | null;
  verified_actual?: string | null;
  budget?: string | null;
  percent_display?: string | null;
  amount_status?: string | null;
  incomplete?: boolean;
  missing_actual?: boolean;
};

export type CloseDraft = {
  draft_id: string;
  period: string;
  version: number;
  content_sha256: string;
  approval_nonce: string | null;
  state: string;
  incomplete: boolean;
  executive_summary: string;
  facts_digest?: string;
  consolidated_usd?: Record<string, string | boolean | null>;
  revenue_by_country_payer?: CloseMoneyRow[];
  expenses_by_country?: CloseMoneyRow[];
  relevant_deviations?: Array<Record<string, unknown>>;
  missing_or_uncertain?: Array<Record<string, unknown>>;
  traceability?: Record<string, unknown>;
  operations?: Array<Record<string, unknown>>;
  figure_ids?: string[];
  fx_rate?: string;
  load_date?: string;
  reviewer_guidance?: string | null;
};

export type CloseJob = {
  job_id: string;
  status: string;
  task_id?: string | null;
  result?: { draft_id?: string };
};

export type CloseFigure = {
  figure_id: string;
  value: string | null;
  formula?: string;
  contributing_rows?: Array<Record<string, unknown>>;
  hash?: string;
  amount_status?: string;
};

export const isNamedTomReviewer = (
  user: Pick<AuthMeResponse, "email" | "role" | "department_id"> | null | undefined,
): boolean =>
  Boolean(
    user &&
      user.email === TOM_CLOSE_EMAIL &&
      user.role === TOM_CLOSE_ROLE &&
      user.department_id === TOM_CLOSE_DEPARTMENT,
  );

export const moneyText = (
  value: string | boolean | null | undefined,
  missing = "missing",
): string => {
  if (value == null || value === false) {
    return missing;
  }
  return String(value);
};

export const lineLabel = (row: CloseMoneyRow): string => {
  const label = row.category ? String(row.category) : String(row.line_id ?? "Line item").replace(/_/g, " ");
  const country = row.country ? String(row.country) : "country not stated";
  const payer = row.payer ? String(row.payer) : "n/a";
  const currency = row.currency ? String(row.currency) : "currency not stated";
  const percent = row.percent_display ? String(row.percent_display) : "percentage unavailable";
  return `${label} · ${country} · ${payer} · ${currency} · actual ${moneyText(row.verified_actual)} · budget ${moneyText(row.budget)} · ${percent} · ${amountStatusLabel(row)}`;
};

export const contributorLabel = (row: Record<string, unknown>, index: number): string => {
  const parts = [
    row.row_id ? `row ${String(row.row_id)}` : `row ${index + 1}`,
    row.ingest_ref ? `ingest ${String(row.ingest_ref)}` : null,
    row.public_entry_id ? `entry ${String(row.public_entry_id)}` : null,
    row.entry_id ? `entry ${String(row.entry_id)}` : null,
    row.line_id ? `line ${String(row.line_id)}` : null,
    row.source_figure_id ? `source figure ${String(row.source_figure_id)}` : null,
    row.value != null ? `value ${String(row.value)}` : null,
  ].filter(Boolean);
  const refs = Array.isArray(row.source_refs)
    ? row.source_refs.map((item) => String(item)).join(", ")
    : row.source_ref
      ? String(row.source_ref)
      : "";
  return refs ? `${parts.join(" · ")} · sources ${refs}` : parts.join(" · ");
};

export const amountStatusLabel = (row: CloseMoneyRow): string => {
  if (row.amount_status === "missing" || row.missing_actual) {
    return "actual missing";
  }
  if (row.amount_status === "known_subtotal" || row.incomplete) {
    return "known subtotal, incomplete";
  }
  if (row.amount_status === "complete") {
    return "complete";
  }
  return row.incomplete ? "known subtotal, incomplete" : "complete";
};

export const listFinancialCloseDrafts = (): Promise<CloseDraft[]> =>
  apiFetch<CloseDraft[]>("/financial-close/drafts", { auth: true });

export const queueFinancialClose = (): Promise<CloseJob> =>
  apiFetch<CloseJob>("/financial-close/run", { method: "POST", auth: true });

export const readFinancialCloseJob = (jobId: string): Promise<CloseJob> =>
  apiFetch<CloseJob>(`/financial-close/jobs/${jobId}`, { auth: true });

export const lookupFinancialCloseFigure = (
  draftId: string,
  figureId: string,
): Promise<CloseFigure> =>
  apiFetch<CloseFigure>(`/financial-close/drafts/${draftId}/figures/${figureId}`, { auth: true });

export const decideFinancialClose = (payload: {
  draft_id: string;
  version: number;
  content_sha256: string;
  approval_nonce: string;
  decision: "approve" | "reject";
  comments?: string;
}): Promise<CloseDraft> =>
  apiFetch<CloseDraft>("/financial-close/approvals", {
    auth: true,
    method: "POST",
    body: JSON.stringify(payload),
  });
