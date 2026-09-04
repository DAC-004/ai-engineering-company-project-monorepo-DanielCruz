import { track } from "@/src/services/telemetry";
import {
  countryFromClinicId,
  daysUntilExpiry,
  EXPIRY_WINDOW_DAYS,
  mapProductCategory,
} from "@/lib/telemetry/mapping";

const expiryFlaggedToday = new Set<string>();
const thresholdOpen = new Set<string>();

const EXPIRY_THROTTLE_STORAGE_KEY = "healthcore.telemetry.expiryFlaggedUtcDays";

const utcDateKey = (): string => new Date().toISOString().slice(0, 10);

const expiryThrottleKey = (productId: number): string =>
  `${productId}:${utcDateKey()}`;

/**
 * Daily expiry throttle must survive a full page reload in the same tab.
 * sessionStorage matches that browser-session scope. A later UTC date uses a
 * different key, so the same product remains eligible the next day.
 */
const readPersistedExpiryKeys = (): Set<string> => {
  if (typeof window === "undefined") {
    return new Set();
  }
  try {
    const raw = window.sessionStorage.getItem(EXPIRY_THROTTLE_STORAGE_KEY);
    if (!raw) {
      return new Set();
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return new Set();
    }
    return new Set(parsed.filter((value): value is string => typeof value === "string"));
  } catch {
    return new Set();
  }
};

const persistExpiryKey = (dayKey: string): void => {
  expiryFlaggedToday.add(dayKey);
  if (typeof window === "undefined") {
    return;
  }
  try {
    const merged = readPersistedExpiryKeys();
    merged.add(dayKey);
    window.sessionStorage.setItem(
      EXPIRY_THROTTLE_STORAGE_KEY,
      JSON.stringify([...merged]),
    );
  } catch {
    // Storage may be unavailable; in-memory throttle still applies this lifetime.
  }
};

const hasExpiryBeenFlaggedToday = (dayKey: string): boolean => {
  if (expiryFlaggedToday.has(dayKey)) {
    return true;
  }
  const persisted = readPersistedExpiryKeys();
  if (persisted.has(dayKey)) {
    expiryFlaggedToday.add(dayKey);
    return true;
  }
  return false;
};

export const trackInboundOrderCreated = (input: {
  clinicId: number;
  productId: number;
  liveCategory: string;
  quantity: number;
  vendorName: string;
  inboundOrderId: number;
  totalCost: number;
}): void => {
  const country = countryFromClinicId(input.clinicId);
  const productCategory = mapProductCategory(input.liveCategory);
  // total_cost is required on inbound_order_created. Emit the submitted
  // form value only when it is finite and >= 0. Zero is valid when the
  // clinician submitted zero. Do not invent a fallback cost.
  if (!country || !productCategory || !Number.isFinite(input.totalCost) || input.totalCost < 0) {
    return;
  }
  track("inbound_order_created", {
    clinic_id: input.clinicId,
    country,
    product_id: input.productId,
    product_category: productCategory,
    quantity: input.quantity,
    vendor_name: input.vendorName,
    inbound_order_id: input.inboundOrderId,
    total_cost: input.totalCost,
  });
};

export const trackOutboundOrderCreated = (input: {
  clinicId: number;
  productId: number;
  liveCategory: string;
  quantity: number;
  department: string;
  outboundOrderId: number;
  consumptionReason?: "clinical_use" | "expiry_waste";
}): void => {
  const country = countryFromClinicId(input.clinicId);
  const productCategory = mapProductCategory(input.liveCategory);
  if (!country || !productCategory) {
    return;
  }
  const properties: Record<string, unknown> = {
    clinic_id: input.clinicId,
    country,
    product_id: input.productId,
    product_category: productCategory,
    quantity: input.quantity,
    department: input.department,
    outbound_order_id: input.outboundOrderId,
  };
  if (input.consumptionReason) {
    properties.consumption_reason = input.consumptionReason;
  }
  track("outbound_order_created", properties);
};

export const trackStockThresholdTriggered = (input: {
  clinicId: number;
  productId: number;
  liveCategory: string;
  remainingQuantity: number;
  minimumStock: number;
  triggeringOutboundOrderId: number;
}): void => {
  if (input.remainingQuantity < 0 || input.remainingQuantity >= input.minimumStock) {
    thresholdOpen.delete(`${input.productId}:${input.clinicId}`);
    return;
  }
  const throttleKey = `${input.productId}:${input.clinicId}`;
  if (thresholdOpen.has(throttleKey)) {
    return;
  }
  const country = countryFromClinicId(input.clinicId);
  const productCategory = mapProductCategory(input.liveCategory);
  if (!country || !productCategory) {
    return;
  }
  track("stock_threshold_triggered", {
    clinic_id: input.clinicId,
    country,
    product_id: input.productId,
    product_category: productCategory,
    quantity: input.remainingQuantity,
    minimum_stock: input.minimumStock,
    triggering_outbound_order_id: input.triggeringOutboundOrderId,
  });
  thresholdOpen.add(throttleKey);
};

export const trackDirectStockEditRejected = (input: {
  clinicId: number;
  productId: number;
  liveCategory: string;
  attemptedQuantity: number;
  httpMethod: "POST" | "PUT" | "PATCH" | "DELETE";
  rejectionReason:
    | "stock_field_forbidden"
    | "method_not_allowed"
    | "direct_write_forbidden";
}): void => {
  const country = countryFromClinicId(input.clinicId);
  const productCategory = mapProductCategory(input.liveCategory);
  if (!country || !productCategory) {
    return;
  }
  track("direct_stock_edit_rejected", {
    clinic_id: input.clinicId,
    country,
    product_id: input.productId,
    product_category: productCategory,
    quantity: input.attemptedQuantity,
    http_method: input.httpMethod,
    route_template: "/inventory/products/{id}",
    rejection_reason: input.rejectionReason,
  });
};

export const trackSupplyExpiryFlagged = (input: {
  clinicId: number;
  productId: number;
  liveCategory: string;
  quantity: number;
  expiryDate: string;
}): void => {
  const untilExpiry = daysUntilExpiry(input.expiryDate);
  if (untilExpiry === null || untilExpiry > EXPIRY_WINDOW_DAYS) {
    return;
  }
  const dayKey = expiryThrottleKey(input.productId);
  if (hasExpiryBeenFlaggedToday(dayKey)) {
    return;
  }
  const country = countryFromClinicId(input.clinicId);
  const productCategory = mapProductCategory(input.liveCategory);
  if (!country || !productCategory || input.quantity < 0) {
    return;
  }
  track("supply_expiry_flagged", {
    clinic_id: input.clinicId,
    country,
    product_id: input.productId,
    product_category: productCategory,
    quantity: input.quantity,
    expiry_date: input.expiryDate,
    days_until_expiry: untilExpiry,
    expiry_window_days: EXPIRY_WINDOW_DAYS,
  });
  persistExpiryKey(dayKey);
};

export const trackOutboundOrderRejected = (input: {
  clinicId: number;
  productId: number;
  liveCategory: string;
  quantity: number;
  availableQuantity: number;
  rejectionReason: "insufficient_stock" | "validation_failed";
  department?: string;
}): void => {
  const country = countryFromClinicId(input.clinicId);
  const productCategory = mapProductCategory(input.liveCategory);
  if (!country || !productCategory) {
    return;
  }
  const properties: Record<string, unknown> = {
    clinic_id: input.clinicId,
    country,
    product_id: input.productId,
    product_category: productCategory,
    quantity: input.quantity,
    available_quantity: input.availableQuantity,
    rejection_reason: input.rejectionReason,
  };
  if (input.department) {
    properties.department = input.department;
  }
  track("outbound_order_rejected", properties);
};
