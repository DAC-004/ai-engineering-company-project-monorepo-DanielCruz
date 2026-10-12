import { clearSessionAndRedirectToLogin } from "@/lib/auth/api";
import { getAccessToken } from "@/lib/auth/token";
import { ApiError } from "@/lib/auth/types";
import {
  NETWORK_ERROR_MESSAGE,
  resolveUserFacingApiText,
  toUserFacingMessage,
} from "@/lib/auth/userFacingError";

export type IncidentAnalysisResult = {
  source_name: string;
  total_records: number;
  valid_count: number;
  invalid_count: number;
  invalid_by_rule: Record<string, number>;
  category_counts: Record<string, number>;
  status_counts: Record<string, number>;
  country_counts: Record<string, number>;
  satisfaction: {
    closed_cases: number;
    scored_cases: number;
    average: number | null;
    score_counts: Record<string, number>;
  };
};

const getBaseUrl = (): string => {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) {
    throw new ApiError("Application configuration is incomplete.", 0);
  }
  return baseUrl.replace(/\/$/, "");
};

const parseErrorResponse = async (response: Response): Promise<string> => {
  try {
    const body = (await response.json()) as { detail?: unknown; message?: unknown };
    if (typeof body.message === "string") {
      return resolveUserFacingApiText(response.status, body.message);
    }
    if (typeof body.detail === "string") {
      return resolveUserFacingApiText(response.status, body.detail);
    }
  } catch {
    // Fall through to status-based copy.
  }
  return toUserFacingMessage(response.status);
};

const authorizedFetch = async (path: string, init: RequestInit): Promise<Response> => {
  const token = getAccessToken();
  if (!token) {
    clearSessionAndRedirectToLogin();
    throw new ApiError(toUserFacingMessage(401), 401);
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${getBaseUrl()}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(NETWORK_ERROR_MESSAGE, 0);
  }

  if (response.status === 401) {
    clearSessionAndRedirectToLogin();
    throw new ApiError(toUserFacingMessage(401), 401);
  }

  return response;
};

/** Upload and analyze an incident CSV (multipart; not JSON). */
export const analyzeIncidentCsv = async (file: File): Promise<IncidentAnalysisResult> => {
  const body = new FormData();
  body.append("file", file, file.name);

  const response = await authorizedFetch("/api/incidents/analyze", {
    method: "POST",
    body,
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorResponse(response), response.status);
  }

  return (await response.json()) as IncidentAnalysisResult;
};

/** Download the last analysis export as CSV text (blob response; not JSON). */
export const downloadIncidentResultsCsv = async (): Promise<{ blob: Blob; filename: string }> => {
  const response = await authorizedFetch("/api/incidents/results/export", {
    method: "GET",
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorResponse(response), response.status);
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/i);
  const filename = match?.[1] ?? "results.csv";
  const blob = await response.blob();
  return { blob, filename };
};
