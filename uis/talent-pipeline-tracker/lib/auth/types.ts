export type UserRole = "admin" | "manager" | "user";

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
