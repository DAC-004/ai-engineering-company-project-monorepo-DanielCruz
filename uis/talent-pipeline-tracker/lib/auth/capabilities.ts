import type { AuthMeResponse, UserRole } from "@/lib/auth/types";

export const canCreateDepartmentRecord = (role: UserRole | null | undefined): boolean =>
  role === "employee" || role === "supervisor" || role === "admin";

export const canUpdateDepartmentRecord = (role: UserRole | null | undefined): boolean =>
  role === "supervisor" || role === "admin";

export const canDeleteSensitiveRecord = (role: UserRole | null | undefined): boolean =>
  role === "admin";

export const canManageAccess = (role: UserRole | null | undefined): boolean =>
  role === "admin";

export const hasCapability = (
  current: AuthMeResponse | null | undefined,
  capability: string,
): boolean => Boolean(current?.capabilities?.includes(capability));
