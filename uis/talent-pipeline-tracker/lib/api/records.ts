import { apiFetch } from "@/lib/api/client";
import type { PaginatedCandidatesResponse } from "@/types/api";
import type {
  Candidate,
  CandidateCreateInput,
  CandidatePatchInput,
  CandidateStage,
  CandidateStatus,
} from "@/types/candidate";

export interface ListRecordsParams {
  status?: CandidateStatus | "";
  stage?: CandidateStage | "";
  search?: string;
  page?: number;
  limit?: number;
}

function buildQuery(params: ListRecordsParams): string {
  const searchParams = new URLSearchParams();

  if (params.status) {
    searchParams.set("status", params.status);
  }

  if (params.stage) {
    searchParams.set("stage", params.stage);
  }

  if (params.search?.trim()) {
    searchParams.set("search", params.search.trim());
  }

  if (params.page) {
    searchParams.set("page", String(params.page));
  }

  if (params.limit) {
    searchParams.set("limit", String(params.limit));
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export async function getRecords(
  params: ListRecordsParams = {},
): Promise<PaginatedCandidatesResponse> {
  return apiFetch<PaginatedCandidatesResponse>(
    `/records${buildQuery(params)}`,
  );
}

export async function getRecord(id: string): Promise<Candidate> {
  return apiFetch<Candidate>(`/records/${id}`);
}

export async function createRecord(
  input: CandidateCreateInput,
): Promise<Candidate> {
  return apiFetch<Candidate>("/records", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateRecord(
  id: string,
  input: CandidateCreateInput,
): Promise<Candidate> {
  return apiFetch<Candidate>(`/records/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function patchRecord(
  id: string,
  input: CandidatePatchInput,
): Promise<Candidate> {
  return apiFetch<Candidate>(`/records/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}
