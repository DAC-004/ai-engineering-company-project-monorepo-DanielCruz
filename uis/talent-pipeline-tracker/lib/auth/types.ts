export type UserRole = "admin" | "supervisor" | "employee" | "manager" | "user";

export type ProfilePublic = {
  id: string;
  user_id: string;
  name: string | null;
  phone: string | null;
  address: string | null;
};

export type AuthMeResponse = {
  email: string;
  role: UserRole;
  department_id: string | null;
  department_name: string | null;
  capabilities: string[];
  profile: ProfilePublic | null;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type UserPublic = {
  id: string;
  email: string;
  is_active: boolean;
  role: UserRole;
  role_id?: UserRole | null;
  department_id?: string | null;
  created_at: string;
};

export type RegisterPayload = {
  email: string;
  password: string;
  name?: string;
  phone?: string;
  address?: string;
};

export type ProfileUpdatePayload = {
  name?: string | null;
  phone?: string | null;
  address?: string | null;
};

export type FieldErrors = Record<string, string>;

export class ApiError extends Error {
  status: number;
  fieldErrors: FieldErrors;

  constructor(message: string, status: number, fieldErrors: FieldErrors = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}
