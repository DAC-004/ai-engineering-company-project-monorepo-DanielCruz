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

export type IncidentTaskLifecycleStatus =
  | "pending"
  | "started"
  | "success"
  | "failure";

type TaskEnqueueResponse = {
  task_id: string;
};

type TaskStatusResponse = {
  task_id: string;
  status: string;
  result?: IncidentAnalysisResult | null;
};

const POLL_INTERVAL_MS = 250;
const POLL_TIMEOUT_MS = 120_000;

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

const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

const isAnalysisResult = (value: unknown): value is IncidentAnalysisResult => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<IncidentAnalysisResult>;
  return (
    typeof candidate.total_records === "number" &&
    typeof candidate.valid_count === "number" &&
    typeof candidate.invalid_count === "number" &&
    typeof candidate.satisfaction === "object" &&
    candidate.satisfaction !== null
  );
};

/**
 * Poll GET /tasks/{task_id} until terminal success/failure (or timeout).
 * 401 during polling clears the session the same way as the upload call.
 */
export const waitForIncidentTaskResult = async (
  taskId: string,
  onStatus?: (status: IncidentTaskLifecycleStatus) => void,
): Promise<IncidentAnalysisResult> => {
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  let lastStatus: string | undefined;

  while (Date.now() < deadline) {
    const response = await authorizedFetch(`/tasks/${encodeURIComponent(taskId)}`, {
      method: "GET",
    });

    if (!response.ok) {
      throw new ApiError(await parseErrorResponse(response), response.status);
    }

    const payload = (await response.json()) as TaskStatusResponse;
    const status = String(payload.status || "pending").toLowerCase();
    if (status !== lastStatus) {
      lastStatus = status;
      if (
        status === "pending" ||
        status === "started" ||
        status === "success" ||
        status === "failure"
      ) {
        onStatus?.(status);
      }
    }

    if (status === "success") {
      if (!isAnalysisResult(payload.result)) {
        throw new ApiError("Analysis completed without a usable result.", 500);
      }
      return payload.result;
    }

    if (status === "failure") {
      throw new ApiError(
        "Incident analysis failed. Review the file and try again.",
        500,
      );
    }

    await sleep(POLL_INTERVAL_MS);
  }

  throw new ApiError(
    "Analysis is still running. Wait a moment and try exporting, or upload again.",
    408,
  );
};

/**
 * Enqueue incident CSV analysis (202 + task_id), then wait for the task result.
 * Multipart upload; not JSON.
 */
export const analyzeIncidentCsv = async (
  file: File,
  onStatus?: (status: IncidentTaskLifecycleStatus) => void,
): Promise<IncidentAnalysisResult> => {
  const body = new FormData();
  body.append("file", file, file.name);

  const response = await authorizedFetch("/api/incidents/analyze", {
    method: "POST",
    body,
  });

  if (response.status !== 202) {
    throw new ApiError(await parseErrorResponse(response), response.status);
  }

  const enqueued = (await response.json()) as TaskEnqueueResponse;
  if (!enqueued.task_id) {
    throw new ApiError("Analysis was accepted without a task id.", 500);
  }

  onStatus?.("pending");
  return waitForIncidentTaskResult(enqueued.task_id, onStatus);
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
