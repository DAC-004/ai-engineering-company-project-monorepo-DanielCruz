import { clearAccessToken, getAccessToken } from "@/lib/auth/token";
import { ApiError, type FieldErrors } from "@/lib/auth/types";

const getBaseUrl = (): string => {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    throw new ApiError(
      "NEXT_PUBLIC_API_BASE_URL is not configured. Copy .env.example to .env.local (use /backend with the Next.js proxy).",
      0,
    );
  }

  return baseUrl.replace(/\/$/, "");
};

/**
 * Parse FastAPI error bodies into a message plus optional field-level errors.
 * Registration (422) returns `detail` as an array of validation objects with `loc`/`msg`.
 */
const parseErrorBody = async (
  response: Response,
): Promise<{ message: string; fieldErrors: FieldErrors }> => {
  const fallback = `Request failed with status ${response.status}`;

  try {
    const body = (await response.json()) as { detail?: unknown };

    if (typeof body.detail === "string") {
      return { message: body.detail, fieldErrors: {} };
    }

    if (Array.isArray(body.detail)) {
      const fieldErrors: FieldErrors = {};
      const messages: string[] = [];

      for (const item of body.detail) {
        if (typeof item !== "object" || item === null) {
          messages.push(String(item));
          continue;
        }

        const entry = item as { loc?: unknown; msg?: unknown };
        const message =
          typeof entry.msg === "string" ? entry.msg : "Invalid value";
        messages.push(message);

        if (Array.isArray(entry.loc)) {
          const fieldName = entry.loc
            .filter((part): part is string => typeof part === "string")
            .filter((part) => part !== "body")
            .at(-1);

          if (fieldName && !fieldErrors[fieldName]) {
            fieldErrors[fieldName] = message;
          }
        }
      }

      return {
        message: messages.join(", ") || fallback,
        fieldErrors,
      };
    }
  } catch {
    // Keep the status fallback when the body is not JSON.
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
  /** Override the AUTH-01 base URL (used by the inventory module). */
  baseUrl?: string;
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
  const { auth = false, json = true, headers, baseUrl, ...rest } = options;
  const root = (baseUrl ?? getBaseUrl()).replace(/\/$/, "");
  const url = `${root}${path.startsWith("/") ? path : `/${path}`}`;

  const requestHeaders = new Headers(headers);

  if (json && !requestHeaders.has("Content-Type") && rest.body) {
    requestHeaders.set("Content-Type", "application/json");
  }

  if (auth) {
    const token = getAccessToken();
    if (!token) {
      clearSessionAndRedirectToLogin();
      throw new ApiError("Authentication required", 401);
    }
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...rest,
    headers: requestHeaders,
  });

  if (response.status === 401 && auth) {
    clearSessionAndRedirectToLogin();
    throw new ApiError("Session expired or unauthorized", 401);
  }

  if (!response.ok) {
    const { message, fieldErrors } = await parseErrorBody(response);
    throw new ApiError(message, response.status, fieldErrors);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
};
