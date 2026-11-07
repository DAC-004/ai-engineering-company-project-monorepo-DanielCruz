"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useCurrentUser } from "@/lib/auth/CurrentUserContext";
import { canViewAudit, listAudit, verifyAudit, type AuditFilters, type AuditPage } from "@/lib/audit";

const emptyFilters: AuditFilters = {};
export function AuditLogPanel() {
  const user = useCurrentUser();
  const allowed = canViewAudit(user);
  const [draft, setDraft] = useState<AuditFilters>(emptyFilters);
  const [applied, setApplied] = useState<AuditFilters>(emptyFilters);
  const [page, setPage] = useState<AuditPage | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [integrity, setIntegrity] = useState("");
  const requestNumber = useRef(0);
  useEffect(() => {
    if (!allowed) return;
    const controller = new AbortController();
    listAudit({}, 0, controller.signal).then((result) => { setPage(result); setBusy(false); }).catch(() => {
      if (!controller.signal.aborted) { setError("Audit metadata could not be loaded. Retry or contact an administrator."); setBusy(false); }
    });
    return () => controller.abort();
  }, [allowed]);
  const load = async (filters: AuditFilters, offset: number) => {
    const request = ++requestNumber.current;
    setBusy(true); setError("");
    try {
      const result = await listAudit(filters, offset);
      if (request === requestNumber.current) { setPage(result); setApplied(filters); }
    } catch { if (request === requestNumber.current) { setPage(null); setError("Audit query could not be completed. Check filters or contact an administrator."); } }
    finally { if (request === requestNumber.current) setBusy(false); }
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const filters = { ...draft };
      if (filters.start) filters.start = new Date(filters.start).toISOString();
      if (filters.end) filters.end = new Date(filters.end).toISOString();
      void load(filters, 0);
    } catch { setError("Enter a valid date range."); }
  };
  if (!allowed) return <section className="panel"><h1>Audit Log</h1><p role="alert">Audit metadata is available only to Admins and department-assigned Supervisors.</p></section>;
  return <section className="panel">
    <h1>Audit Log</h1>
    <p>Accountability metadata only. Clinical contents, patient names and notes are excluded.</p>
    <p>{user?.role === "admin" ? "Scope: all departments" : `Scope: ${user?.department_name ?? user?.department_id}`}</p>
    <form onSubmit={submit}>
      {([ ["actor_ref", "Actor reference"], ["action", "Action code"], ["resource_kind", "Resource type"], ["resource_ref", "Resource reference"] ] as const).map(([key, label]) => <label key={key}>{label}<input value={draft[key] ?? ""} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} /></label>)}
      <label>From (local time)<input type="datetime-local" value={draft.start ?? ""} onChange={(event) => setDraft({ ...draft, start: event.target.value })} /></label>
      <label>To (local time)<input type="datetime-local" value={draft.end ?? ""} onChange={(event) => setDraft({ ...draft, end: event.target.value })} /></label>
      <button type="submit" disabled={busy}>Apply filters</button>
      <button type="button" disabled={busy} onClick={() => { setDraft({}); void load({}, 0); }}>Clear filters</button>
    </form>
    {user?.role === "admin" ? <button type="button" disabled={busy} onClick={() => {
      setIntegrity("Checking integrity…");
      void verifyAudit().then((result) => setIntegrity(result.valid ? `Integrity verified: ${result.checked} entries.` : "Integrity check failed. Contact an administrator.")).catch(() => setIntegrity("Integrity could not be verified. Contact an administrator."));
    }}>Verify ledger integrity</button> : null}
    {integrity ? <p role="status">{integrity}</p> : null}
    {busy ? <p role="status">Loading audit metadata…</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    {page ? <>
      <p>{page.total} matching entries. Showing {page.items.length ? page.offset + 1 : 0}–{page.offset + page.items.length}.</p>
      <div style={{ overflowX: "auto" }}><table><caption>Immutable audit metadata</caption><thead><tr>{["Time (UTC)", "Actor", "Action", "Resource", "Patient reference", "Department", "Context", "Origin", "Outcome"].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>
        {page.items.map((entry) => <tr key={entry.seq}><td>{entry.occurred_at}</td><td>{entry.actor_kind}: {entry.actor_ref}</td><td>{entry.action}</td><td>{entry.resource_kind}: {entry.resource_ref ?? "—"}</td><td>{entry.patient_ref ?? "—"}</td><td>{entry.department_id ?? "—"}</td><td>{entry.context}</td><td>{entry.origin}</td><td>{entry.outcome}</td></tr>)}
      </tbody></table></div>
      {!page.items.length ? <p>No matching entries.</p> : null}
      <nav aria-label="Audit pagination"><button disabled={busy || page.offset === 0} onClick={() => void load(applied, Math.max(0, page.offset - page.limit))}>Previous</button><button disabled={busy || !page.has_more} onClick={() => void load(applied, page.offset + page.limit)}>Next</button></nav>
    </> : null}
  </section>;
}
