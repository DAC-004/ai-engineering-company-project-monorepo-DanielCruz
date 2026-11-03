import { ApiError } from "@/lib/auth/types";

export const AMBIGUOUS_CREATE_MESSAGE =
  "The create request may already have reached the server. Check the user list before submitting again.";

export const REPEAT_AFTER_SUCCESS_MESSAGE =
  "That account was already created in this form. Change the email before creating another.";

export const PENDING_CREATE_MESSAGE = "Creating account…";

export type CreateSubmitDecision = "submit" | "pending" | "repeat";

export const createRequestSignature = (input: {
  email: string;
  roleId: string;
  departmentId: string;
}): string =>
  `${input.email.trim().toLowerCase()}|${input.roleId}|${input.departmentId}`;

export const decideCreateSubmit = (input: {
  pending: boolean;
  inFlight?: boolean;
  lastSuccessSignature: string | null;
  nextSignature: string;
}): CreateSubmitDecision => {
  // inFlight is a synchronous ref; React pending state is not visible until
  // the current submit handler yields, so two clicks in one turn both see
  // pending=false unless this flag is set before the first await.
  if (input.pending || input.inFlight) {
    return "pending";
  }
  if (
    input.lastSuccessSignature !== null &&
    input.lastSuccessSignature === input.nextSignature
  ) {
    return "repeat";
  }
  return "submit";
};

export const messageForCreateFailure = (
  error: ApiError,
): { message: string; ambiguous: boolean } => {
  if (error.status === 0) {
    return { message: AMBIGUOUS_CREATE_MESSAGE, ambiguous: true };
  }
  return { message: error.message, ambiguous: false };
};
