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

/** Mirror `packages/shared/manager_constants.py` (incident manager allowed values). */
const INCIDENT_CATEGORIES = [
  "clinical_equipment",
  "it_system",
  "billing_error",
  "compliance_breach",
  "patient_experience",
  "staff_issue",
  "facility_issue",
  "referral_issue",
  "other",
] as const;

const INCIDENT_STATUSES = [
  "open",
  "in_progress",
  "resolved",
  "discarded",
] as const;

const INCIDENT_ORIGINS = ["customer", "branch", "internal"] as const;

const INCIDENT_BRANCHES = [
  "central",
  "austin_north",
  "dallas_uptown",
  "houston_med_center",
  "san_antonio_west",
  "miami_brickell",
  "miami_doral",
  "orlando_east",
  "tampa_bay",
  "atlanta_midtown",
  "savannah",
  "london_city",
  "london_west",
  "manchester_central",
] as const;

/** Mirror `shared/incident_analyzer/analyze.py` REQUIRED_COLUMNS. */
const INCIDENT_CSV_REQUIRED_COLUMNS = new Set([
  "incident_id",
  "date",
  "clinic_id",
  "country",
  "category",
  "description",
  "status",
  "patient_id",
  "satisfaction_score",
]);

const INCIDENT_STATUS_TRANSITIONS: Record<
  (typeof INCIDENT_STATUSES)[number],
  ReadonlySet<(typeof INCIDENT_STATUSES)[number]>
> = {
  open: new Set(["in_progress", "discarded"]),
  in_progress: new Set(["resolved", "discarded"]),
  resolved: new Set(),
  discarded: new Set(),
};

/** Fixed API `detail` / `message` strings verified in services/api (not status-based trust). */
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
  "Only an admin can change roles",
  "If that address is registered, you'll receive a link shortly",
  "The submitted text was not stored.",
  "That incident was not found.",
  "This irreversible action requires explicit confirmation.",
  "The CSV file is empty.",
  "The CSV file has no header row.",
  "The CSV file contains no data rows.",
  "The CSV file could not be parsed. Check the file format and try again.",
  "Incorrect file format: only CSV files are accepted.",
  "Incorrect file format: file must be UTF-8 encoded CSV.",
  "No analysis available. Upload a CSV to /api/incidents/analyze first.",
  "Body must be JSON",
  "Body must be a JSON object",
  "Request body is required",
  "The question is empty. Provide a HealthCore support question before retrieval.",
  "Model request rate limit exceeded. Retry later.",
  "An unexpected error occurred. Please try again.",
  "Medical supply not found",
  "A medical supply with this SKU already exists.",
  "clinic_id must be between 1 and 12",
  "The knowledge request could not be processed.",
  "The knowledge assistant could not generate an answer right now.",
  "Stock cannot be modified directly. Record an inbound or outbound order.",
  "stock and current_stock cannot be written. Record an inbound or outbound order.",
]);

/** `services/api/app/schemas/incident.py` + `main.py` manager validation labels. */
const INCIDENT_MANAGER_FIELD_LABELS: Record<string, string> = {
  title: "Title",
  description: "Description",
  category: "Category",
  status: "Status",
  origin: "Origin",
  branch: "Branch",
  request: "This request",
};

const buildMustBeOneOfMessage = (
  label: string,
  values: readonly string[],
): string => `${label} must be one of: ${values.join(", ")}.`;

const MANAGER_ALLOWED_MESSAGES = new Set<string>();

for (const field of Object.keys(INCIDENT_MANAGER_FIELD_LABELS)) {
  const label = INCIDENT_MANAGER_FIELD_LABELS[field];
  MANAGER_ALLOWED_MESSAGES.add(`${label} is required.`);
  MANAGER_ALLOWED_MESSAGES.add(`${label} is not valid.`);
}

MANAGER_ALLOWED_MESSAGES.add("The request body must be valid JSON.");
MANAGER_ALLOWED_MESSAGES.add(
  buildMustBeOneOfMessage("Category", INCIDENT_CATEGORIES),
);
MANAGER_ALLOWED_MESSAGES.add(
  buildMustBeOneOfMessage("Status", INCIDENT_STATUSES),
);
MANAGER_ALLOWED_MESSAGES.add(
  buildMustBeOneOfMessage("Origin", INCIDENT_ORIGINS),
);
MANAGER_ALLOWED_MESSAGES.add(
  buildMustBeOneOfMessage("Branch", INCIDENT_BRANCHES),
);

/** `suppliers.py` — TinyDB doc id is numeric only. */
const SUPPLIER_NOT_FOUND_PATTERN = /^Supplier \d+ not found$/;

const CSV_MISSING_COLUMNS_PREFIX =
  "Incorrect CSV format: missing required columns: ";

const UNSAFE_ERROR_PATTERNS: RegExp[] = [
  /traceback/i,
  /\bFile "/i,
  /\.py\b/i,
  /\.ts\b/i,
  /\/var\//i,
  /\\Users\\/i,
  /\bat line \d+/i,
  /\bException:/i,
  /\bError:\s/,
  /\bstack\b/i,
  /\bsecret\b/i,
];

const isUnsafeErrorText = (raw: string): boolean =>
  UNSAFE_ERROR_PATTERNS.some((pattern) => pattern.test(raw));

const isAllowedCsvMissingColumnsMessage = (raw: string): boolean => {
  if (!raw.startsWith(CSV_MISSING_COLUMNS_PREFIX)) {
    return false;
  }
  const suffix = raw.slice(CSV_MISSING_COLUMNS_PREFIX.length);
  if (!suffix) {
    return false;
  }
  const columns = suffix.split(", ").map((part) => part.trim());
  return (
    columns.length > 0 &&
    columns.every((column) => INCIDENT_CSV_REQUIRED_COLUMNS.has(column))
  );
};

const isAllowedIncidentStatusTransitionMessage = (raw: string): boolean => {
  const finalMatch =
    /^A (open|in_progress|resolved|discarded) incident is final and cannot change status\.$/.exec(
      raw,
    );
  if (finalMatch) {
    return true;
  }

  const moveMatch =
    /^An (open|in_progress|resolved|discarded) incident can only move to: (.+)\.$/.exec(
      raw,
    );
  if (!moveMatch) {
    return false;
  }

  const fromStatus = moveMatch[1] as (typeof INCIDENT_STATUSES)[number];
  const permitted = INCIDENT_STATUS_TRANSITIONS[fromStatus];
  if (!permitted || permitted.size === 0) {
    return false;
  }

  const targets = moveMatch[2].split(", ").map((part) => part.trim());
  if (targets.length !== permitted.size) {
    return false;
  }

  return targets.every(
    (target) =>
      (INCIDENT_STATUSES as readonly string[]).includes(target) &&
      permitted.has(target as (typeof INCIDENT_STATUSES)[number]),
  );
};

const matchesSourceBackedManagerMessage = (raw: string): boolean => {
  if (MANAGER_ALLOWED_MESSAGES.has(raw)) {
    return true;
  }
  if (isAllowedCsvMissingColumnsMessage(raw)) {
    return true;
  }
  if (isAllowedIncidentStatusTransitionMessage(raw)) {
    return true;
  }
  if (SUPPLIER_NOT_FOUND_PATTERN.test(raw)) {
    return true;
  }
  return false;
};

const STATUS_MESSAGES: Record<number, string> = {
  400: "The request could not be completed. Check your information and try again.",
  401: "Your session expired. Please sign in again.",
  403: "You do not have permission to do that.",
  404: "The requested information could not be found.",
  409: "An account with this email already exists.",
  422: "Please review the highlighted fields and try again.",
  500: GENERIC_ERROR_MESSAGE,
};

const statusFallbackMessage = (status: number): string =>
  STATUS_MESSAGES[status] ?? GENERIC_ERROR_MESSAGE;

/**
 * Map a raw API error string to UI-safe copy. Whitelist and source-backed manager
 * messages only; never trust status code or JSON key alone.
 */
export const resolveUserFacingApiText = (
  status: number,
  raw: string | undefined,
): string => {
  const trimmed = raw?.trim() ?? "";
  if (!trimmed || isUnsafeErrorText(trimmed)) {
    return statusFallbackMessage(status);
  }
  if (SAFE_API_DETAILS.has(trimmed) || matchesSourceBackedManagerMessage(trimmed)) {
    return trimmed;
  }
  return statusFallbackMessage(status);
};

export const toUserFacingMessage = (
  status: number,
  rawDetail?: string,
): string => {
  if (rawDetail) {
    return resolveUserFacingApiText(status, rawDetail);
  }
  return STATUS_MESSAGES[status] ?? GENERIC_ERROR_MESSAGE;
};

/** Summary shown above inline field errors (I02 register / inventory forms). */
export const VALIDATION_FORM_SUMMARY_MESSAGE = STATUS_MESSAGES[422];

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
