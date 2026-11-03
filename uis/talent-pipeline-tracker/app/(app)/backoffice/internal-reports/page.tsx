"use client";

import { FormEvent, useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import { useCurrentUser } from "@/lib/auth/CurrentUserContext";
import { canCreateDepartmentRecord } from "@/lib/auth/capabilities";
import {
  createInternalReport,
  listInternalReports,
  type InternalReport,
} from "@/lib/access";

export default function InternalReportsPage() {
  const currentUser = useCurrentUser();
  const canCreate = canCreateDepartmentRecord(currentUser?.role);
  const [reports, setReports] = useState<InternalReport[]>([]);
  const [status, setStatus] = useState("Loading reports…");
  const [kind, setKind] = useState<"" | "ok" | "error">("");

  const applyReports = (rows: InternalReport[]) => {
    setReports(rows);
    setStatus(`Showing ${rows.length} report(s) for the visible department scope.`);
    setKind("ok");
  };

  const load = async () => {
    try {
      applyReports(await listInternalReports());
    } catch (error) {
      setReports([]);
      setStatus(error instanceof ApiError ? error.message : "Unable to load reports.");
      setKind("error");
    }
  };

  useEffect(() => {
    let cancelled = false;
    void listInternalReports()
      .then((rows) => {
        if (cancelled) {
          return;
        }
        applyReports(rows);
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setReports([]);
        setStatus(error instanceof ApiError ? error.message : "Unable to load reports.");
        setKind("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await createInternalReport({
        title: String(data.get("title") || ""),
        body: String(data.get("body") || ""),
      });
      form.reset();
      await load();
    } catch (error) {
      setStatus(error instanceof ApiError ? error.message : "Create failed.");
      setKind("error");
    }
  };

  return (
    <section className="home-panel">
      <p className="eyebrow">Department notes</p>
      <h1>Internal reports</h1>
      <p className="home-lede">
        Lists are department-scoped. Admin sees every department. Employee and Supervisor see their
        own department only.
      </p>
      <p role="status" className={kind === "error" ? "form-error" : "field-hint"}>
        {status}
      </p>
      <ul>
        {reports.map((report) => (
          <li key={report.id}>
            <strong>{report.title}</strong> — {report.department_id}
            <p>{report.body}</p>
          </li>
        ))}
      </ul>
      {canCreate ? (
        <form className="supplier-register-form" onSubmit={handleCreate}>
          <label>
            Title
            <input name="title" required />
          </label>
          <label>
            Body
            <textarea name="body" required />
          </label>
          <button type="submit" className="btn-primary">
            Create report
          </button>
        </form>
      ) : null}
    </section>
  );
}
