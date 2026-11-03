"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import { useCurrentUser } from "@/lib/auth/CurrentUserContext";
import { canManageAccess } from "@/lib/auth/capabilities";
import {
  assignUserAccess,
  createDepartment,
  createRole,
  listAdminUsers,
  listDepartments,
  listRoles,
  updateDepartment,
  updateRole,
  type DepartmentRecord,
  type RoleRecord,
} from "@/lib/access";
import type { UserPublic, UserRole } from "@/lib/auth/types";

export default function AccessAdminPage() {
  const currentUser = useCurrentUser();
  const allowed = canManageAccess(currentUser?.role);
  const [status, setStatus] = useState(allowed ? "Loading access catalog…" : "");
  const [kind, setKind] = useState<"" | "ok" | "error">("");
  const [roles, setRoles] = useState<RoleRecord[]>([]);
  const [departments, setDepartments] = useState<DepartmentRecord[]>([]);
  const [users, setUsers] = useState<UserPublic[]>([]);

  const applyCatalog = (
    roleRows: RoleRecord[],
    departmentRows: DepartmentRecord[],
    userRows: UserPublic[],
  ) => {
    setRoles(roleRows);
    setDepartments(departmentRows);
    setUsers(userRows);
    setStatus("Access catalog loaded.");
    setKind("ok");
  };

  const load = async () => {
    try {
      const [roleRows, departmentRows, userRows] = await Promise.all([
        listRoles(),
        listDepartments(),
        listAdminUsers(),
      ]);
      applyCatalog(roleRows, departmentRows, userRows);
    } catch (error) {
      setRoles([]);
      setDepartments([]);
      setUsers([]);
      setStatus(error instanceof ApiError ? error.message : "Unable to load access catalog.");
      setKind("error");
    }
  };

  useEffect(() => {
    if (!allowed) {
      return;
    }
    let cancelled = false;
    void Promise.all([listRoles(), listDepartments(), listAdminUsers()])
      .then(([roleRows, departmentRows, userRows]) => {
        if (cancelled) {
          return;
        }
        applyCatalog(roleRows, departmentRows, userRows);
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setRoles([]);
        setDepartments([]);
        setUsers([]);
        setStatus(error instanceof ApiError ? error.message : "Unable to load access catalog.");
        setKind("error");
      });
    return () => {
      cancelled = true;
    };
  }, [allowed]);

  if (!allowed) {
    return (
      <section className="home-panel">
        <p className="eyebrow">Administration</p>
        <h1>Roles and departments</h1>
        <p className="form-error" role="status">
          Insufficient role permissions
        </p>
      </section>
    );
  }

  const handleCreateRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await createRole({
        code: String(data.get("code") || ""),
        name: String(data.get("name") || ""),
        rank: Number(data.get("rank")),
      });
      form.reset();
      await load();
    } catch (error) {
      setStatus(error instanceof ApiError ? error.message : "Role create failed.");
      setKind("error");
    }
  };

  const handleCreateDepartment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await createDepartment({
        code: String(data.get("code") || ""),
        name: String(data.get("name") || ""),
      });
      form.reset();
      await load();
    } catch (error) {
      setStatus(error instanceof ApiError ? error.message : "Department create failed.");
      setKind("error");
    }
  };

  const handleAssign = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const userId = String(data.get("user_id") || "");
    const roleId = String(data.get("role_id") || "");
    const departmentId = String(data.get("department_id") || "");
    const payload: { role_id?: UserRole; department_id?: string } = {};
    if (roleId) payload.role_id = roleId as UserRole;
    if (departmentId) payload.department_id = departmentId;
    try {
      await assignUserAccess(userId, payload);
      form.reset();
      await load();
    } catch (error) {
      setStatus(error instanceof ApiError ? error.message : "Assignment failed.");
      setKind("error");
    }
  };

  return (
    <section className="home-panel">
      <p className="eyebrow">Administration</p>
      <h1>Roles and departments</h1>
      <p className="home-lede">
        Role and department are independent. Changing one assignment does not change the other.
      </p>
      <p>
        <Link href="/backoffice/access/create">Create account</Link>
      </p>
      <p role="status" className={kind === "error" ? "form-error" : "field-hint"}>
        {status}
      </p>

      <h2>Roles</h2>
      <ul>
        {roles.map((role) => (
          <li key={role.id}>
            {role.name} ({role.code}, rank {role.rank}){" "}
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                const name = window.prompt("Display name", role.name);
                if (!name) return;
                void updateRole(role.id, { name }).then(load).catch((error: unknown) => {
                  setStatus(error instanceof ApiError ? error.message : "Role update failed.");
                  setKind("error");
                });
              }}
            >
              Edit name
            </button>
          </li>
        ))}
      </ul>
      <form className="supplier-register-form" onSubmit={handleCreateRole}>
        <label>
          Code
          <input name="code" required />
        </label>
        <label>
          Name
          <input name="name" required />
        </label>
        <label>
          Rank
          <input name="rank" type="number" min={1} max={3} required />
        </label>
        <button type="submit" className="btn-primary">
          Create role
        </button>
      </form>

      <h2>Departments</h2>
      <ul>
        {departments.map((department) => (
          <li key={department.id}>
            {department.name} ({department.code}){" "}
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                const name = window.prompt("Display name", department.name);
                if (!name) return;
                void updateDepartment(department.id, { name })
                  .then(load)
                  .catch((error: unknown) => {
                    setStatus(
                      error instanceof ApiError ? error.message : "Department update failed.",
                    );
                    setKind("error");
                  });
              }}
            >
              Edit name
            </button>
          </li>
        ))}
      </ul>
      <form className="supplier-register-form" onSubmit={handleCreateDepartment}>
        <label>
          Code
          <input name="code" required />
        </label>
        <label>
          Name
          <input name="name" required />
        </label>
        <button type="submit" className="btn-primary">
          Create department
        </button>
      </form>

      <h2>Independent assignment</h2>
      <ul>
        {users.map((user) => (
          <li key={user.id}>
            {user.email} — role {user.role_id ?? user.role} — department {user.department_id ?? "none"}
          </li>
        ))}
      </ul>
      <form className="supplier-register-form" onSubmit={handleAssign}>
        <label>
          User
          <select name="user_id" required>
            <option value="">Select user</option>
            {users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.email}
              </option>
            ))}
          </select>
        </label>
        <label>
          Role
          <select name="role_id">
            <option value="">Leave unchanged</option>
            {roles.map((role) => (
              <option key={role.id} value={role.code}>
                {role.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Department
          <select name="department_id">
            <option value="">Leave unchanged</option>
            {departments.map((department) => (
              <option key={department.id} value={department.code}>
                {department.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn-primary">
          Assign independently
        </button>
      </form>
    </section>
  );
}
