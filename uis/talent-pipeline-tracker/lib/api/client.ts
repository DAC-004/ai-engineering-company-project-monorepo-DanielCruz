import { ApiError } from "@/types/api";

function getBaseUrl(): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    throw new ApiError(
      "NEXT_PUBLIC_API_BASE_URL is not configured. Copy .env.example to .env.local.",
      0,
    );
  }

  return baseUrl.replace(/\/$/, "");
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${getBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail
          .map((item) => {
            if (
              typeof item === "object" &&
              item !== null &&
              "msg" in item &&
              typeof item.msg === "string"
            ) {
              return item.msg;
            }
            return String(item);
          })
          .join(", ");
      }
    } catch {
      // Keep default message when response body is not JSON.
    }

    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
