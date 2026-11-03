import { apiFetch } from "@/lib/auth/api";
import type { UserPublic, UserRole } from "@/lib/auth/types";

export type RoleRecord = {
  id: string;
  code: string;
  name: string;
  rank: number;
};

export type DepartmentRecord = {
  id: string;
  code: string;
  name: string;
};

export type InternalReport = {
  id: string;
  department_id: string;
  title: string;
  body: string;
  created_by: string;
  created_at: string;
};

export const listRoles = (): Promise<RoleRecord[]> =>
  apiFetch<RoleRecord[]>("/roles", { auth: true, method: "GET" });

export const listDepartments = (): Promise<DepartmentRecord[]> =>
  apiFetch<DepartmentRecord[]>("/departments", { auth: true, method: "GET" });

export const createRole = (payload: {
  code: string;
  name: string;
  rank: number;
}): Promise<RoleRecord> =>
  apiFetch<RoleRecord>("/roles", {
    auth: true,
    method: "POST",
    body: JSON.stringify(payload),
  });

export const updateRole = (
  roleId: string,
  payload: { name?: string; rank?: number },
): Promise<RoleRecord> =>
  apiFetch<RoleRecord>(`/roles/${roleId}`, {
    auth: true,
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const createDepartment = (payload: {
  code: string;
  name: string;
}): Promise<DepartmentRecord> =>
  apiFetch<DepartmentRecord>("/departments", {
    auth: true,
    method: "POST",
    body: JSON.stringify(payload),
  });

export const updateDepartment = (
  departmentId: string,
  payload: { name?: string },
): Promise<DepartmentRecord> =>
  apiFetch<DepartmentRecord>(`/departments/${departmentId}`, {
    auth: true,
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const listAdminUsers = (): Promise<UserPublic[]> =>
  apiFetch<UserPublic[]>("/users", { auth: true, method: "GET" });

export type AdminUserCreatePayload = {
  email: string;
  password: string;
  role_id?: UserRole;
  department_id?: string;
  name?: string;
  phone?: string;
  address?: string;
};

export const createAdminUser = (
  payload: AdminUserCreatePayload,
): Promise<UserPublic> =>
  apiFetch<UserPublic>("/users", {
    auth: true,
    method: "POST",
    body: JSON.stringify(payload),
  });

export const assignUserAccess = (
  userId: string,
  payload: { role_id?: UserRole; department_id?: string },
): Promise<UserPublic> =>
  apiFetch<UserPublic>(`/users/${userId}/assignment`, {
    auth: true,
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const listInternalReports = (): Promise<InternalReport[]> =>
  apiFetch<InternalReport[]>("/internal-reports", { auth: true, method: "GET" });

export const createInternalReport = (payload: {
  title: string;
  body: string;
  department_id?: string;
}): Promise<InternalReport> =>
  apiFetch<InternalReport>("/internal-reports", {
    auth: true,
    method: "POST",
    body: JSON.stringify(payload),
  });
