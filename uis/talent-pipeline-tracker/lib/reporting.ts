import { apiFetch } from "@/lib/auth/api";

/**
 * Business reporting client for the Monthly Clinic Supply Performance Report.
 *
 * Calls GET /reporting/monthly-clinic-supply-performance from Part 2.
 * This module must not call GET /telemetry/report.
 */

export type ClinicSupplyPerformance = {
  clinic_id: string;
  country: string;
  total_supply_cost: number;
  supply_consumption_count: number;
  critical_stockout_count: number;
  expiry_risk_count: number;
  currency: string;
};

export type MonthlyClinicSupplyPerformanceResponse = {
  month_start: string;
  clinics: ClinicSupplyPerformance[];
};

export const getMonthlyClinicSupplyPerformance = (
  monthStart?: string,
): Promise<MonthlyClinicSupplyPerformanceResponse> => {
  const query =
    monthStart === undefined || monthStart === ""
      ? ""
      : `?month_start=${encodeURIComponent(monthStart)}`;
  return apiFetch<MonthlyClinicSupplyPerformanceResponse>(
    `/reporting/monthly-clinic-supply-performance${query}`,
    { method: "GET", auth: true },
  );
};
