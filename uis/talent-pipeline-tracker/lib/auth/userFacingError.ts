import type { FieldErrors } from "@/lib/auth/types";

export const SUPPORT_EMAIL = "care@healthcore.com";

export const NETWORK_ERROR_MESSAGE =
  "Unable to reach the server. Check your connection and try again.";

export const CONFIG_ERROR_MESSAGE =
  `The application cannot reach the API. Try again or contact support at ${SUPPORT_EMAIL}.`;

export const GENERIC_ERROR_MESSAGE =
  `Something went wrong. Please try again or contact support at ${SUPPORT_EMAIL}.`;

export const MISSING_TOKEN_MESSAGE =
  `Sign-in did not complete. Please try again or contact support at ${SUPPORT_EMAIL}.`;

const SAFE_API_DETAILS = new Set([
  "Incorrect email or password",
  "Inactive user",
  "A user with this email already exists.",
  "User not found",
  "Profile not found",
  "Could not validate credentials",
  "Not authorized to access this resource",
  "Not authorized to modify this analysis",
  "Not authenticated",
]);

const STATUS_MESSAGES: Record<number, string> = {
  400: "The request could not be completed. Check your information and try again.",
  401: "Your session expired. Please sign in again.",
  403: "You do not have permission to do that.",
  404: "The requested information could not be found.",
  409: "An account with this email already exists.",
  422: "Please review the highlighted fields and try again.",
  500: GENERIC_ERROR_MESSAGE,
};

export const toUserFacingMessage = (
  status: number,
  rawDetail?: string,
): string => {
  if (rawDetail && SAFE_API_DETAILS.has(rawDetail)) {
    return rawDetail;
  }
  return STATUS_MESSAGES[status] ?? GENERIC_ERROR_MESSAGE;
};

export const toUserFacingFieldErrors = (
  fieldErrors: FieldErrors,
): FieldErrors => {
  const mapped: FieldErrors = {};

  for (const field of Object.keys(fieldErrors)) {
    if (field === "email") {
      mapped[field] = "Enter a valid email address.";
    } else if (field === "password") {
      mapped[field] = "Password must be at least 8 characters.";
    } else {
      mapped[field] = "This field is invalid. Please check it and try again.";
    }
  }

  return mapped;
};
