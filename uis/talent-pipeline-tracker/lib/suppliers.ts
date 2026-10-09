import { apiFetch } from "@/lib/auth/api";

/** Mirrors `VALID_CATEGORIES` in `services/api/app/schemas/supplier.py`. */
export const VALID_SUPPLIER_CATEGORIES = [
  "medical_supplies",
  "laboratory_services",
  "pharmaceutical",
  "clinical_software",
  "it_infrastructure",
  "hr_and_payroll_software",
  "cleaning_and_facilities",
  "patient_communication",
  "billing_and_coding_software",
  "training_platforms",
] as const;

export type SupplierStatus = "active" | "suspended";
export type SupplierCountry = "USA" | "UK";
export type SupplierCurrency = "USD" | "GBP";
export type ComplianceAgreement = "BAA" | "DPA" | "both";

export type SupplierRecord = {
  id: number;
  name: string;
  country: SupplierCountry;
  categories: string[];
  monthly_rate: number;
  currency: SupplierCurrency;
  updated_at: string;
  status: SupplierStatus;
  compliance_agreement: ComplianceAgreement | null;
  contract_renewal_date: string | null;
  contact_email: string | null;
  notes: string | null;
};

export type SupplierCreatePayload = {
  name: string;
  country: SupplierCountry;
  categories: string[];
  monthly_rate: number;
  currency: SupplierCurrency;
  status: SupplierStatus;
  compliance_agreement?: ComplianceAgreement | null;
  contract_renewal_date?: string | null;
  contact_email?: string | null;
  notes?: string | null;
};

export type SupplierListFilters = {
  country?: string;
  category?: string;
};

const buildQuery = (filters?: SupplierListFilters): string => {
  const params = new URLSearchParams();
  if (filters?.country) {
    params.set("country", filters.country);
  }
  if (filters?.category) {
    params.set("category", filters.category);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
};

/** Public list endpoint; no bearer required. */
export const listSuppliers = async (
  filters?: SupplierListFilters,
): Promise<SupplierRecord[]> => {
  return apiFetch<SupplierRecord[]>(`/suppliers${buildQuery(filters)}`);
};

export const createSupplier = async (
  payload: SupplierCreatePayload,
): Promise<SupplierRecord> => {
  return apiFetch<SupplierRecord>("/suppliers", {
    method: "POST",
    auth: true,
    body: JSON.stringify(payload),
  });
};

export const updateSupplierRate = async (
  supplierId: number,
  monthlyRate: number,
): Promise<SupplierRecord> => {
  return apiFetch<SupplierRecord>(`/suppliers/${supplierId}/rate`, {
    method: "PATCH",
    auth: true,
    body: JSON.stringify({ monthly_rate: monthlyRate }),
  });
};

export const updateSupplierStatus = async (
  supplierId: number,
  status: SupplierStatus,
): Promise<SupplierRecord> => {
  return apiFetch<SupplierRecord>(`/suppliers/${supplierId}/status`, {
    method: "PATCH",
    auth: true,
    body: JSON.stringify({ status }),
  });
};
