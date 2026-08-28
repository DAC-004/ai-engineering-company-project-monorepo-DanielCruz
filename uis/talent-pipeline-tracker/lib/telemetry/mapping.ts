/**
 * Live-system to telemetry-contract mapping from docs/telemetry/telemetry-plan.md
 * section 2.3. Emit CONTEXT enums, never live catalog strings.
 */

export const LIVE_CATEGORY_TO_PRODUCT_CATEGORY: Record<
  string,
  "medication" | "ppe" | "consumable" | "equipment"
> = {
  medications: "medication",
  consumables: "consumable",
  wound_care: "consumable",
  ppe: "ppe",
  diagnostics: "equipment",
  medication: "medication",
  consumable: "consumable",
  equipment: "equipment",
};

export const mapProductCategory = (
  liveCategory: string,
): "medication" | "ppe" | "consumable" | "equipment" | null =>
  LIVE_CATEGORY_TO_PRODUCT_CATEGORY[liveCategory] ?? null;

export const countryFromClinicId = (clinicId: number): "US" | "UK" | null => {
  if (clinicId >= 1 && clinicId <= 9) {
    return "US";
  }
  if (clinicId >= 10 && clinicId <= 12) {
    return "UK";
  }
  return null;
};

export const EXPIRY_WINDOW_DAYS = 30;

export const toRoutePath = (pathname: string): string => {
  const path = pathname.split("?")[0] || "/";
  return path.startsWith("/") ? path : `/${path}`;
};

export const toApiRouteTemplate = (path: string): string => {
  const normalized = toRoutePath(path);
  return normalized
    .replace(/\/inventory\/products\/\d+/g, "/inventory/products/{id}")
    .replace(/\/users\/[0-9a-fA-F-]+/g, "/users/{id}");
};

export const sanitizeTelemetryMessage = (raw: string): string => {
  const withoutEmail = raw.replace(
    /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi,
    "[redacted]",
  );
  const withoutToken = withoutEmail.replace(
    /Bearer\s+[A-Za-z0-9\-._~+/]+=*/gi,
    "Bearer [redacted]",
  );
  const trimmed = withoutToken.replace(/\s+/g, " ").trim();
  if (!trimmed) {
    return "redacted";
  }
  return trimmed.slice(0, 180);
};

export const daysUntilExpiry = (
  expiryDate: string,
  from: Date = new Date(),
): number | null => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(expiryDate);
  if (!match) {
    return null;
  }
  const expiry = Date.UTC(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
  );
  const start = Date.UTC(
    from.getUTCFullYear(),
    from.getUTCMonth(),
    from.getUTCDate(),
  );
  const diffDays = Math.floor((expiry - start) / 86_400_000);
  if (diffDays < 0) {
    return null;
  }
  return diffDays;
};
