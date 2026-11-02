"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import { useCurrentUser } from "@/lib/auth/CurrentUserContext";
import { canManageAccess } from "@/lib/auth/capabilities";
import {
  createAdminUser,
  listDepartments,
  listRoles,
  type DepartmentRecord,
  type RoleRecord,
} from "@/lib/access";
import {
  AMBIGUOUS_CREATE_MESSAGE,
  PENDING_CREATE_MESSAGE,
  REPEAT_AFTER_SUCCESS_MESSAGE,
  createRequestSignature,
  decideCreateSubmit,
  messageForCreateFailure,
} from "@/lib/access/createAccountForm";
import type { UserRole } from "@/lib/auth/types";

export default function CreateAccountPage() {
  const currentUser = useCurrentUser();
  const allowed = canManageAccess(currentUser?.role);
  const [status, setStatus] = useState(allowed ? "Loading access catalog…" : "");
  const [kind, setKind] = useState<"" | "ok" | "error">("");
  const [roles, setRoles] = useState<RoleRecord[]>([]);
  const [departments, setDepartments] = useState<DepartmentRecord[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [roleId, setRoleId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [pending, setPending] = useState(false);
  const [lastSuccessSignature, setLastSuccessSignature] = useState<string | null>(
    null,
  );
  const passwordRef = useRef<HTMLInputElement>(null);
  const submitInFlightRef = useRef(false);

  const clearPassword = () => {
    setPassword("");
    if (passwordRef.current) {
      passwordRef.current.value = "";
    }
  };

  useEffect(() => {
    if (!allowed) {
      return;
    }
    let cancelled = false;
    void Promise.all([listRoles(), listDepartments()])
      .then(([roleRows, departmentRows]) => {
        if (cancelled) {
          return;
        }
        setRoles(roleRows);
        setDepartments(departmentRows);
        setStatus("Select a role and department independently, then create the account.");
        setKind("ok");
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setRoles([]);
        setDepartments([]);
        setStatus(error instanceof ApiError ? error.message : "Unable to load access catalog.");
        setKind("error");
      });
    return () => {
      cancelled = true;
      setPassword("");
    };
  }, [allowed]);

  if (!allowed) {
    return (
      <section className="home-panel">
        <p className="eyebrow">Administration</p>
        <h1>Create account</h1>
        <p className="form-error" role="status">
          Insufficient role permissions
        </p>
      </section>
    );
  }

  const handleCancel = () => {
    if (pending) {
      setStatus("A create request is already in progress and cannot be reversed here.");
      setKind("error");
      return;
    }
    setEmail("");
    setRoleId("");
    setDepartmentId("");
    clearPassword();
    setKind("");
    setStatus("Creation cancelled. No request was sent.");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextSignature = createRequestSignature({
      email,
      roleId,
      departmentId,
    });
    const decision = decideCreateSubmit({
      pending,
      inFlight: submitInFlightRef.current,
      lastSuccessSignature,
      nextSignature,
    });
    if (decision === "pending") {
      return;
    }
    if (decision === "repeat") {
      clearPassword();
      setStatus(REPEAT_AFTER_SUCCESS_MESSAGE);
      setKind("error");
      return;
    }

    submitInFlightRef.current = true;
    setPending(true);
    setStatus(PENDING_CREATE_MESSAGE);
    setKind("");
    try {
      const created = await createAdminUser({
        email: email.trim(),
        password,
        role_id: roleId as UserRole,
        ...(departmentId ? { department_id: departmentId } : {}),
      });
      setLastSuccessSignature(nextSignature);
      clearPassword();
      setKind("ok");
      setStatus(`Account created: ${created.email}`);
    } catch (error) {
      clearPassword();
      if (error instanceof ApiError) {
        const failure = messageForCreateFailure(error);
        setStatus(failure.message);
        setKind("error");
        return;
      }
      setStatus(AMBIGUOUS_CREATE_MESSAGE);
      setKind("error");
    } finally {
      submitInFlightRef.current = false;
      setPending(false);
    }
  };

  return (
    <section className="home-panel">
      <p className="eyebrow">Administration</p>
      <h1>Create account</h1>
      <p className="home-lede">
        Admin-only account creation. Role and department are independent
        selections from the existing catalogs. Public registration stays disabled.
      </p>
      <p>
        <Link href="/backoffice/access">Back to roles and departments</Link>
      </p>
      <p role="status" className={kind === "error" ? "form-error" : "field-hint"}>
        {status}
      </p>
      <form className="supplier-register-form" onSubmit={handleSubmit} autoComplete="off">
        <label htmlFor="create-account-email">
          Email
          <input
            id="create-account-email"
            name="email"
            type="email"
            autoComplete="off"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={pending}
          />
        </label>
        <label htmlFor="create-account-password">
          Password
          <input
            id="create-account-password"
            ref={passwordRef}
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={pending}
          />
        </label>
        <label htmlFor="create-account-role">
          Role
          <select
            id="create-account-role"
            name="role_id"
            required
            value={roleId}
            onChange={(event) => setRoleId(event.target.value)}
            disabled={pending}
          >
            <option value="">Select role</option>
            {roles.map((role) => (
              <option key={role.id} value={role.code}>
                {role.name}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="create-account-department">
          Department
          <select
            id="create-account-department"
            name="department_id"
            value={departmentId}
            onChange={(event) => setDepartmentId(event.target.value)}
            disabled={pending}
          >
            <option value="">No department</option>
            {departments.map((department) => (
              <option key={department.id} value={department.code}>
                {department.name}
              </option>
            ))}
          </select>
        </label>
        <div className="supplier-register-actions">
          <button type="submit" className="btn-primary" disabled={pending}>
            {pending ? "Creating…" : "Create account"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleCancel}
            disabled={pending}
          >
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
