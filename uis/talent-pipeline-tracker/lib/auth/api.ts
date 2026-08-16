import { clearAccessToken, getAccessToken } from "@/lib/auth/token";
import { ApiError, type FieldErrors } from "@/lib/auth/types";
import {
  CONFIG_ERROR_MESSAGE,
  GENERIC_ERROR_MESSAGE,
  NETWORK_ERROR_MESSAGE,
  toUserFacingFieldErrors,
  toUserFacingMessage,
} from "@/lib/auth/userFacingError";

const getBaseUrl = (): string => {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    throw new ApiError(CONFIG_ERROR_MESSAGE, 0);
  }

  return baseUrl.replace(/\/$/, "");
};

/**
 * Parse FastAPI error bodies into a user-safe message plus optional field errors.
 * Raw status text, parser errors, and implementation details never reach the UI.
 */
const parseErrorBody = async (
  response: Response,
): Promise<{ message: string; fieldErrors: FieldErrors }> => {
  const fallback = toUserFacingMessage(response.status);

  try {
    const body = (await response.json()) as { detail?: unknown };

    if (typeof body.detail === "string") {
      return {
        message: toUserFacingMessage(response.status, body.detail),
        fieldErrors: {},
      };
    }

    if (Array.isArray(body.detail)) {
      const fieldErrors: FieldErrors = {};

      for (const item of body.detail) {
        if (typeof item !== "object" || item === null) {
          continue;
        }

        const entry = item as { loc?: unknown; msg?: unknown };
        if (!Array.isArray(entry.loc)) {
          continue;
        }

        const fieldName = entry.loc
          .filter((part): part is string => typeof part === "string")
          .filter((part) => part !== "body")
          .at(-1);

        if (fieldName && !fieldErrors[fieldName]) {
          fieldErrors[fieldName] =
            typeof entry.msg === "string" ? entry.msg : "Invalid value";
        }
      }

      return {
        message: toUserFacingMessage(response.status),
        fieldErrors: toUserFacingFieldErrors(fieldErrors),
      };
    }
  } catch {
    // Non-JSON bodies use the status-mapped fallback, never a parse error.
  }

  return { message: fallback, fieldErrors: {} };
};

/**
 * Clear the local JWT and send the browser to /login.
 * Used by logout and by any protected API call that receives HTTP 401.
 */
export const clearSessionAndRedirectToLogin = (): void => {
  clearAccessToken();

  if (typeof window === "undefined") {
    return;
  }

  const loginPath = "/login";
  if (window.location.pathname !== loginPath) {
    window.location.assign(loginPath);
  }
};

type ApiFetchOptions = RequestInit & {
  /** When true, attach Authorization: Bearer <token> from localStorage. */
  auth?: boolean;
  /** Override Content-Type / skip JSON default (needed for OAuth2 form login). */
  json?: boolean;
};

/**
 * Browser fetch helper for the HealthCore API.
 *
 * Protected calls (`auth: true`) read the JWT from localStorage and send
 * `Authorization: Bearer <token>`. Any HTTP 401 clears the session and redirects
 * to /login, matching the AUTH-02 token lifecycle.
 */
export const apiFetch = async <T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> => {
  const { auth = false, json = true, headers, ...rest } = options;
  const url = `${getBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;

  const requestHeaders = new Headers(headers);

  if (json && !requestHeaders.has("Content-Type") && rest.body) {
    requestHeaders.set("Content-Type", "application/json");
  }

  if (auth) {
    const token = getAccessToken();
    if (!token) {
      clearSessionAndRedirectToLogin();
      throw new ApiError(toUserFacingMessage(401), 401);
    }
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...rest,
      headers: requestHeaders,
    });
  } catch {
    throw new ApiError(NETWORK_ERROR_MESSAGE, 0);
  }

  if (response.status === 401 && auth) {
    clearSessionAndRedirectToLogin();
    throw new ApiError(toUserFacingMessage(401), 401);
  }

  if (!response.ok) {
    const { message, fieldErrors } = await parseErrorBody(response);
    throw new ApiError(message, response.status, fieldErrors);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(GENERIC_ERROR_MESSAGE, response.status);
  }
};
