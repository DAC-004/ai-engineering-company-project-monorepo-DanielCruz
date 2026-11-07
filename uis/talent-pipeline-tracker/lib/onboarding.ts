import { apiFetch } from "@/lib/auth/api";
import { ApiError } from "@/lib/auth/types";

export type OnboardingSummary = {
  onboarding_id: string;
  display_name?: string;
  office?: string;
  department_id?: string;
  current_stage: number;
  stage_name: string;
  status: string;
  pending_kind: string;
  blocked: boolean;
  last_action: string;
  last_rejection_comment?: string;
  decision_nonce?: string;
  hire_user_id?: string;
  paperwork_received?: boolean;
  background_check_completed?: boolean;
  content?: { document_id: string; title: string; body: string };
  questions?: Array<{
    id: string;
    prompt: string;
    choices: string[];
    topic: string;
    source_document: string;
  }>;
};

export type AcceptedJob = {
  accepted: boolean;
  task_id: string;
  onboarding_id: string;
  actor_type: string;
};

export type OnboardingJob = {
  task_id: string;
  state: string;
  ready: boolean;
  actor_type?: string;
};

const JOB_SUCCESS = "SUCCESS";
const JOB_FAILURE_STATES = new Set(["FAILURE", "REVOKED", "REJECTED"]);

const delay = (ms: number, signal?: AbortSignal) => {
  if (signal?.aborted) {
    return Promise.reject(new ApiError("Onboarding job wait was cancelled.", 499));
  }
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => resolve(), ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new ApiError("Onboarding job wait was cancelled.", 499));
      },
      { once: true },
    );
  });
};

export const waitForOnboardingJob = async (
  taskId: string,
  options?: { timeoutMs?: number; intervalMs?: number; signal?: AbortSignal },
): Promise<OnboardingJob> => {
  const timeoutMs = options?.timeoutMs ?? 30_000;
  const intervalMs = options?.intervalMs ?? 400;
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (options?.signal?.aborted) {
      throw new ApiError("Onboarding job wait was cancelled.", 499);
    }
    const job = await getOnboardingJob(taskId);
    const state = job.state.toUpperCase();
    if (state === JOB_SUCCESS) {
      return job;
    }
    if (JOB_FAILURE_STATES.has(state)) {
      throw new ApiError(`Onboarding job ended with ${state}.`, 409);
    }
    await delay(intervalMs, options?.signal);
  }
  throw new ApiError("Onboarding job timed out.", 408);
};

export const listOnboardings = () =>
  apiFetch<OnboardingSummary[]>("/onboarding", { method: "GET", auth: true });

export const getOnboarding = (onboardingId: string) =>
  apiFetch<OnboardingSummary>(`/onboarding/${onboardingId}`, { method: "GET", auth: true });

export const getMyOnboarding = () =>
  apiFetch<OnboardingSummary>("/onboarding/me", { method: "GET", auth: true });

export const getOnboardingJob = (taskId: string) =>
  apiFetch<OnboardingJob>(`/onboarding/jobs/${taskId}`, {
    method: "GET",
    auth: true,
  });

export const submitPaperwork = (
  onboardingId: string,
  payload: {
    documents_received: boolean;
    background_check_completed: boolean;
    decision_nonce: string;
  },
) =>
  apiFetch<AcceptedJob>(`/onboarding/${onboardingId}/paperwork`, {
    method: "POST",
    auth: true,
    body: JSON.stringify(payload),
  });

export const submitCheck = (
  onboardingId: string,
  payload: { answers: number[]; decision_nonce: string },
) =>
  apiFetch<AcceptedJob>(`/onboarding/${onboardingId}/check`, {
    method: "POST",
    auth: true,
    body: JSON.stringify(payload),
  });

export const submitDecision = (
  onboardingId: string,
  payload: { decision: "approve" | "reject"; comment: string; decision_nonce: string },
) =>
  apiFetch<AcceptedJob>(`/onboarding/${onboardingId}/decision`, {
    method: "POST",
    auth: true,
    body: JSON.stringify(payload),
  });

export const askOnboardingQuestion = (onboardingId: string, question: string) =>
  apiFetch(`/onboarding/${onboardingId}/questions`, {
    method: "POST",
    auth: true,
    body: JSON.stringify({ question }),
  });

export const requestOnboardingAccess = (onboardingId: string, system_id: string) =>
  apiFetch(`/onboarding/${onboardingId}/access-requests`, {
    method: "POST",
    auth: true,
    body: JSON.stringify({ system_id }),
  });
