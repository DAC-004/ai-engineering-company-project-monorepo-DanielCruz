import type { Candidate } from "./candidate";
import type { Note } from "./note";

export interface PaginatedCandidatesResponse {
  total: number;
  page: number;
  limit: number;
  data: Candidate[];
}

export interface NotesListResponse {
  data: Note[];
  meta: {
    total: number;
  };
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}
