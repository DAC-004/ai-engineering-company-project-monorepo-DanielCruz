import { apiFetch } from "@/lib/auth/api";
import type { AuthMeResponse } from "@/lib/auth/types";

export type AuditEntry = {
  seq: number; actor_kind: "human" | "process" | "anonymous"; actor_ref: string;
  action: string; resource_kind: string; resource_ref: string | null;
  patient_ref: string | null; department_id: string | null; occurred_at: string;
  origin: string; context: string; outcome: string; operation_ref: string;
};
export type AuditFilters = { actor_ref?: string; action?: string; resource_kind?: string; resource_ref?: string; start?: string; end?: string };
export type AuditPage = { items: AuditEntry[]; total: number; has_more: boolean; limit: number; offset: number };
export const canViewAudit = (user: AuthMeResponse | null | undefined): boolean =>
  Boolean(user?.capabilities.includes("read_audit_log") && (user.role === "admin" || (user.role === "supervisor" && user.department_id)));
export const auditQuery = (filters: AuditFilters, offset = 0, limit = 25): string => {
  if (!Number.isInteger(limit) || limit < 1 || limit > 100 || !Number.isInteger(offset) || offset < 0 || offset > 100000) throw new Error("Invalid page bounds");
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  for (const [key, value] of Object.entries(filters)) if (value?.trim()) query.set(key, value.trim());
  return query.toString();
};
export const listAudit = (filters: AuditFilters, offset = 0, signal?: AbortSignal): Promise<AuditPage> =>
  apiFetch<AuditPage>(`/audit-log?${auditQuery(filters, offset)}`, { auth: true, signal });
export const verifyAudit = (): Promise<{ valid: boolean; checked: number }> =>
  apiFetch("/audit-log/integrity", { auth: true });
