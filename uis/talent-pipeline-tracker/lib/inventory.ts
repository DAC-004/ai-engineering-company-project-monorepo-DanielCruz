import { apiFetch } from "@/lib/auth/api";
import { ApiError } from "@/lib/auth/types";

/**
 * Central Inventory API client.
 *
 * All `/inventory` calls go through this module. Components must not call
 * `fetch` directly. Protected requests reuse `apiFetch`, which attaches
 * `Authorization: Bearer <token>` from localStorage.
 */

export type MedicalSupply = {
  id: number;
  name: string;
  sku: string;
  category: string;
  unit: string;
  country: string;
  current_stock: number;
};

export type SupplyDelivery = {
  id: number;
  supply_id: number;
  quantity: number;
  vendor_name: string;
  clinic_id: number;
  created_at: string;
  user_uuid: string;
};

export type SupplyConsumption = {
  id: number;
  supply_id: number;
  quantity: number;
  consumption_type: string;
  clinic_id: number;
  created_at: string;
  user_uuid: string;
};

export type InventoryOrderType = "delivery" | "consumption";

export type InventoryOrder = {
  id: number;
  order_type: InventoryOrderType;
  supply_id: number;
  supply_name: string;
  supply_sku: string;
  supply_category: string;
  supply_unit: string;
  supply_country: string;
  quantity: number;
  clinic_id: number;
  created_at: string;
  user_uuid: string;
  vendor_name: string | null;
  consumption_type: string | null;
};

export type SupplyDeliveryCreatePayload = {
  supply_id: number;
  quantity: number;
  vendor_name: string;
  clinic_id: number;
};

export type SupplyConsumptionCreatePayload = {
  supply_id: number;
  quantity: number;
  consumption_type: ConsumptionType;
  clinic_id: number;
};

export type ConsumptionType = "clinical_use" | "expiry_waste";

export const CONSUMPTION_TYPES: readonly ConsumptionType[] = [
  "clinical_use",
  "expiry_waste",
];

export const CLINIC_ID_MIN = 1;
export const CLINIC_ID_MAX = 12;

export const CLINIC_IDS: readonly number[] = Array.from(
  { length: CLINIC_ID_MAX - CLINIC_ID_MIN + 1 },
  (_, index) => CLINIC_ID_MIN + index,
);

/**
 * Visual stock-level thresholds for the medical-supplies table.
 *
 * These values are a HealthCore operations UX convention only. They do not
 * change API behavior. The backend remains authoritative for whether a
 * SupplyConsumption may be recorded (`current_stock` is computed server-side).
 *
 * - depleted: current_stock === 0 (no units available for clinical use)
 * - low: 1 <= current_stock <= 10 (at or below a one-shift buffer)
 * - healthy: current_stock > 10
 */
export const LOW_STOCK_MAX = 10;

export type StockLevel = "depleted" | "low" | "healthy";

export const getStockLevel = (currentStock: number): StockLevel => {
  if (currentStock <= 0) {
    return "depleted";
  }
  if (currentStock <= LOW_STOCK_MAX) {
    return "low";
  }
  return "healthy";
};

export const STOCK_LEVEL_LABEL: Record<StockLevel, string> = {
  depleted: "Depleted",
  low: "Low stock",
  healthy: "Healthy",
};

export const CATEGORY_LABEL: Record<string, string> = {
  ppe: "PPE",
  wound_care: "Wound care",
  diagnostics: "Diagnostics",
  medications: "Medications",
  consumables: "Consumables",
};

export const CONSUMPTION_TYPE_LABEL: Record<ConsumptionType, string> = {
  clinical_use: "Clinical use",
  expiry_waste: "Expiry waste",
};

export const formatCategory = (category: string): string =>
  CATEGORY_LABEL[category] ?? category;

export const formatConsumptionType = (consumptionType: string): string =>
  CONSUMPTION_TYPE_LABEL[consumptionType as ConsumptionType] ?? consumptionType;

export const formatCountryJurisdiction = (country: string): string => {
  if (country === "US") {
    return "US";
  }
  if (country === "UK") {
    return "UK";
  }
  return country;
};

const getInventoryBaseUrl = (): string => {
  const configured =
    process.env.NEXT_PUBLIC_INVENTORY_API_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!configured) {
    throw new ApiError(
      "NEXT_PUBLIC_INVENTORY_API_URL is not configured. Copy .env.example to .env.local.",
      0,
    );
  }

  return configured.replace(/\/$/, "");
};

const inventoryFetch = <T>(path: string, options: RequestInit = {}): Promise<T> =>
  apiFetch<T>(path, {
    ...options,
    auth: true,
    baseUrl: getInventoryBaseUrl(),
  });

export const listMedicalSupplies = (): Promise<MedicalSupply[]> =>
  inventoryFetch<MedicalSupply[]>("/inventory/products", { method: "GET" });

export const getMedicalSupply = (supplyId: number): Promise<MedicalSupply> =>
  inventoryFetch<MedicalSupply>(`/inventory/products/${supplyId}`, {
    method: "GET",
  });

export const createSupplyDelivery = (
  payload: SupplyDeliveryCreatePayload,
): Promise<SupplyDelivery> =>
  inventoryFetch<SupplyDelivery>("/inventory/orders/inbound", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const createSupplyConsumption = (
  payload: SupplyConsumptionCreatePayload,
): Promise<SupplyConsumption> =>
  inventoryFetch<SupplyConsumption>("/inventory/orders/outbound", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const listInventoryOrders = (): Promise<InventoryOrder[]> =>
  inventoryFetch<InventoryOrder[]>("/inventory/orders", { method: "GET" });
