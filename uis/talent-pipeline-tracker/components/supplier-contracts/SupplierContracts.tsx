"use client";

import { useEffect, useState } from "react";

import { useCurrentUser } from "@/lib/auth/CurrentUserContext";
import { hasCapability } from "@/lib/auth/capabilities";
import { ApiError } from "@/lib/auth/types";
import {
  askSupplierContract,
  approveSupplierContractDraft,
  confirmSupplierContractDpa,
  listContractAlerts,
  listContractDrafts,
  listContractSuppliers,
  type SupplierContractAlert,
  type SupplierContractAskPayload,
  type SupplierContractDraft,
  type SupplierContractRecord,
} from "@/lib/supplier-contracts";

const QUESTIONS = [
  "What alternatives exist in the same country and category?",
  "When is the non-renewal notice deadline?",
  "Write a renegotiation brief with notice, exit, and sources.",
  "Write a communication to the supplier.",
];

const NAMED_APPROVER_BY_EMAIL: Record<string, string> = {
  "marcus.clinical@healthcore.example": "marcus.reid",
  "claire.compliance@healthcore.example": "claire.whitfield",
  "sandra.executive@healthcore.example": "sandra.okonkwo",
};

export const SupplierContracts = () => {
  const currentUser = useCurrentUser();
  const namedApprover = currentUser?.email
    ? NAMED_APPROVER_BY_EMAIL[currentUser.email.toLowerCase()]
    : undefined;
  const canApprove = hasCapability(currentUser, "approve_department_record");
  const canConfirmDpa =
    canApprove && (currentUser?.department_id === "compliance" || currentUser?.role === "admin");
  const [suppliers, setSuppliers] = useState<SupplierContractRecord[]>([]);
  const [alerts, setAlerts] = useState<SupplierContractAlert[]>([]);
  const [drafts, setDrafts] = useState<SupplierContractDraft[]>([]);
  const [supplierId, setSupplierId] = useState("HC-S03");
  const [question, setQuestion] = useState(QUESTIONS[0]);
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState<"" | "ok" | "error">("");
  const [payload, setPayload] = useState<SupplierContractAskPayload | null>(null);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([listContractSuppliers(), listContractAlerts(), listContractDrafts()]).then(
      ([records, rows, persisted]) => {
        if (cancelled) {
          return;
        }
        setSuppliers(records);
        setAlerts(rows);
        setDrafts(persisted);
        setSelectedDraftId((current) => {
          if (current && persisted.some((draft) => draft.draft_id === current)) {
            return current;
          }
          return persisted[0]?.draft_id ?? null;
        });
      },
      (error: unknown) => {
        if (cancelled) {
          return;
        }
        setKind("error");
        setStatus(error instanceof ApiError ? error.message : "Unable to load supplier contracts.");
      },
    );
    return () => {
      cancelled = true;
    };
  }, [currentUser?.email]);

  const applyWorkspace = async (preferredDraftId?: string | null) => {
    const [records, rows, persisted] = await Promise.all([
      listContractSuppliers(),
      listContractAlerts(),
      listContractDrafts(),
    ]);
    setSuppliers(records);
    setAlerts(rows);
    setDrafts(persisted);
    const nextId =
      (preferredDraftId && persisted.some((draft) => draft.draft_id === preferredDraftId)
        ? preferredDraftId
        : null) ??
      persisted[0]?.draft_id ??
      null;
    setSelectedDraftId(nextId);
    return persisted;
  };

  const handleAsk = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    setKind("");
    setStatus("Asking the supervisor…");
    try {
      const response = await askSupplierContract({
        supplier_id: supplierId,
        question,
      });
      setPayload(response.payload);
      await applyWorkspace(response.payload.draft?.draft_id ?? selectedDraftId);
      setStatus(response.payload.blocked ? "Request blocked." : "Answer ready.");
      setKind(response.payload.blocked ? "error" : "ok");
    } catch (error) {
      setKind("error");
      setStatus(error instanceof ApiError ? error.message : "Unable to ask the supervisor.");
    } finally {
      setBusy(false);
    }
  };

  const draft = drafts.find((item) => item.draft_id === selectedDraftId) ?? null;
  const remainingForCaller =
    namedApprover !== undefined &&
    draft !== null &&
    draft.state === "pending" &&
    draft.required.includes(namedApprover) &&
    !draft.granted.includes(namedApprover);
  const pendingForSupplier = drafts.some(
    (item) => item.supplier_id === supplierId && item.state === "pending",
  );
  const askDisabled = busy || pendingForSupplier;
  const approveDisabled = busy || !canApprove || !remainingForCaller;

  const handleApprove = async () => {
    if (!draft || busy || approveDisabled) {
      return;
    }
    setBusy(true);
    try {
      const updated = await approveSupplierContractDraft(draft);
      await applyWorkspace(updated.draft_id);
      setStatus("Approval recorded.");
      setKind("ok");
    } catch (error) {
      setKind("error");
      setStatus(error instanceof ApiError ? error.message : "Approval was not accepted.");
    } finally {
      setBusy(false);
    }
  };

  const handleDpa = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    try {
      await confirmSupplierContractDpa(supplierId);
      await applyWorkspace(selectedDraftId);
      setStatus("Compliance confirmation recorded.");
      setKind("ok");
    } catch (error) {
      setKind("error");
      setStatus(error instanceof ApiError ? error.message : "DPA confirmation was not accepted.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="home-panel inventory-panel">
      <h1>Supplier contracts</h1>
      <p className="field-hint">
        Prices and contract terms are specialist outputs. Drafts stay internal until named approvers act.
      </p>
      <p role="status" className={kind === "error" ? "form-error" : "field-hint"} aria-live="polite">
        {status}
      </p>
      <label>
        Supplier
        <select value={supplierId} onChange={(event) => setSupplierId(event.target.value)} disabled={askDisabled}>
          {suppliers.map((supplier) => (
            <option key={supplier.supplier_id} value={supplier.supplier_id}>
              {supplier.supplier_id} {supplier.display_name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Question
        <select value={question} onChange={(event) => setQuestion(event.target.value)} disabled={askDisabled}>
          {QUESTIONS.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="btn-primary" onClick={() => void handleAsk()} disabled={askDisabled}>
        Ask
      </button>
      {payload ? (
        <section aria-labelledby="answer-heading">
          <h2 id="answer-heading">Answer</h2>
          <p>{payload.answer}</p>
          <p>Approvers: {(payload.required_approvers || []).join(", ") || "none"}</p>
          <ul>
            {(payload.citations || []).map((citation) => (
              <li key={citation}>{citation}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {payload?.blocked && payload.block_reason === "missing_dpa_blocks_brief_and_draft" && canConfirmDpa ? (
        <section aria-labelledby="dpa-heading">
          <h2 id="dpa-heading">Compliance confirmation</h2>
          <p>A missing DPA blocks the brief and draft until Compliance confirms.</p>
          <button type="button" className="btn-secondary" onClick={() => void handleDpa()} disabled={busy}>
            Confirm DPA proceed
          </button>
        </section>
      ) : null}
      <section aria-labelledby="draft-heading">
        <h2 id="draft-heading">Internal drafts</h2>
        {drafts.length === 0 ? <p>No drafts assigned to you.</p> : null}
        {drafts.length > 0 ? (
          <label>
            Draft
            <select
              value={selectedDraftId ?? ""}
              onChange={(event) => setSelectedDraftId(event.target.value || null)}
              disabled={busy}
            >
              {drafts.map((item) => (
                <option key={item.draft_id} value={item.draft_id}>
                  {item.display_name || item.supplier_id} {item.state}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {draft ? (
          <>
            <p>{draft.display_name || draft.supplier_id}</p>
            <p>{draft.body}</p>
            <p>Required: {draft.required.join(", ") || "none"}</p>
            <p>Granted: {draft.granted.join(", ") || "none"}</p>
            <p>Status: {draft.state}</p>
            {canApprove && remainingForCaller ? (
              <button type="button" className="btn-secondary" onClick={() => void handleApprove()} disabled={approveDisabled}>
                Approve
              </button>
            ) : null}
          </>
        ) : null}
      </section>
      <section aria-labelledby="alerts-heading">
        <h2 id="alerts-heading">Internal alerts</h2>
        <ul>
          {alerts.length === 0 ? <li>No alerts.</li> : null}
          {alerts.map((alert) => (
            <li key={alert.id}>
              {alert.kind} {alert.supplier_id} {alert.recipient}
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
};
