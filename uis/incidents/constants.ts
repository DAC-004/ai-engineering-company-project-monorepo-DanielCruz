export const CATEGORIES = [
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

export const STATUSES = [
  "open",
  "in_progress",
  "resolved",
  "discarded",
] as const;

export const ORIGINS = ["customer", "branch", "internal"] as const;

export const BRANCHES = [
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

export const BRANCH_LABELS: Record<(typeof BRANCHES)[number], string> = {
  central: "Central — Austin Main Clinic",
  austin_north: "Austin — North",
  dallas_uptown: "Dallas Uptown",
  houston_med_center: "Houston Medical Center",
  san_antonio_west: "San Antonio West",
  miami_brickell: "Miami Brickell",
  miami_doral: "Miami Doral",
  orlando_east: "Orlando East",
  tampa_bay: "Tampa Bay",
  atlanta_midtown: "Atlanta Midtown",
  savannah: "Savannah",
  london_city: "London City",
  london_west: "London West End",
  manchester_central: "Manchester Central",
};

export const CATEGORY_LABELS: Record<(typeof CATEGORIES)[number], string> = {
  clinical_equipment: "Clinical equipment",
  it_system: "IT system",
  billing_error: "Billing error",
  compliance_breach: "Compliance breach",
  patient_experience: "Patient experience",
  staff_issue: "Staff issue",
  facility_issue: "Facility issue",
  referral_issue: "Referral issue",
  other: "Other",
};

export const STATUS_LABELS: Record<(typeof STATUSES)[number], string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  discarded: "Discarded",
};

export const ORIGIN_LABELS: Record<(typeof ORIGINS)[number], string> = {
  customer: "Customer",
  branch: "Branch",
  internal: "Internal",
};

export const ALLOWED_TRANSITIONS: Record<
  (typeof STATUSES)[number],
  ReadonlyArray<(typeof STATUSES)[number]>
> = {
  open: ["in_progress", "discarded"],
  in_progress: ["resolved", "discarded"],
  resolved: [],
  discarded: [],
};

export const DEFAULT_CREATE_STATUS = "open";
export const DEFAULT_BRANCH = "central";
