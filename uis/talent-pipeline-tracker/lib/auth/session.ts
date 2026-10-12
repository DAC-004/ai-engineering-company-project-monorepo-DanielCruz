import { apiFetch } from "@/lib/auth/api";
import { clearAccessToken, setAccessToken } from "@/lib/auth/token";
import { ApiError } from "@/lib/auth/types";
import { MISSING_TOKEN_MESSAGE } from "@/lib/auth/userFacingError";
import type {
  AuthMeResponse,
  ProfilePublic,
  ProfileUpdatePayload,
  RegisterPayload,
  TokenResponse,
  UserPublic,
} from "@/lib/auth/types";

const requireAccessToken = (tokenResponse: TokenResponse): TokenResponse => {
  const accessToken = tokenResponse?.access_token;
  if (!accessToken) {
    throw new ApiError(MISSING_TOKEN_MESSAGE, 0);
  }
  return tokenResponse;
};

/**
 * Authenticate against POST /auth/login.
 *
 * The API uses OAuth2PasswordRequestForm: `username` is the account email,
 * and the body must be application/x-www-form-urlencoded (not JSON).
 */
export const loginWithPassword = async (
  email: string,
  password: string,
): Promise<TokenResponse> => {
  const formBody = new URLSearchParams();
  formBody.set("username", email);
  formBody.set("password", password);

  const tokenResponse = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    json: false,
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formBody.toString(),
  });
  return requireAccessToken(tokenResponse);
};

/**
 * Register via POST /users (optional profile fields), then immediately
 * log in so the frontend ends with a JWT in localStorage.
 */
export const registerAndAuthenticate = async (
  payload: RegisterPayload,
): Promise<TokenResponse> => {
  const body: RegisterPayload = {
    email: payload.email,
    password: payload.password,
  };

  if (payload.name?.trim()) {
    body.name = payload.name.trim();
  }
  if (payload.phone?.trim()) {
    body.phone = payload.phone.trim();
  }
  if (payload.address?.trim()) {
    body.address = payload.address.trim();
  }

  await apiFetch<UserPublic>("/users", {
    method: "POST",
    body: JSON.stringify(body),
  });

  return requireAccessToken(
    await loginWithPassword(payload.email, payload.password),
  );
};

export const storeSessionToken = (token: string): void => {
  setAccessToken(token);
};

export const logout = (): void => {
  clearAccessToken();
};

export const fetchCurrentUser = (): Promise<AuthMeResponse> =>
  apiFetch<AuthMeResponse>("/auth/me", { auth: true, method: "GET" });

export const updateMyProfile = (
  payload: ProfileUpdatePayload,
): Promise<ProfilePublic> =>
  apiFetch<ProfilePublic>("/profiles/me", {
    auth: true,
    method: "PUT",
    body: JSON.stringify(payload),
  });

export type PasswordActionResponse = {
  detail: string;
};

/** POST /auth/forgot-password — always succeeds outwardly (anti-enumeration). */
export const requestPasswordReset = (
  email: string,
): Promise<PasswordActionResponse> =>
  apiFetch<PasswordActionResponse>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });

/** POST /auth/reset-password — consumes the one-time token from the email link. */
export const resetPasswordWithToken = (
  token: string,
  newPassword: string,
): Promise<PasswordActionResponse> =>
  apiFetch<PasswordActionResponse>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });

/** POST /auth/change-password — authenticated; verifies current password first. */
export const changePassword = (
  currentPassword: string,
  newPassword: string,
): Promise<PasswordActionResponse> =>
  apiFetch<PasswordActionResponse>("/auth/change-password", {
    auth: true,
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
