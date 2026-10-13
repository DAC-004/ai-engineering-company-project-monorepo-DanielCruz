"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import {
  getMonthlyClinicSupplyPerformance,
  type ClinicSupplyPerformance,
  type MonthlyClinicSupplyPerformanceResponse,
} from "@/lib/reporting";

const MONTH_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

const formatReportMonth = (monthStart: string): string => {
  const [year, month] = monthStart.split("-").map(Number);
  if (!year || !month) {
    return monthStart;
  }
  return MONTH_FORMATTER.format(Date.UTC(year, month - 1, 1));
};

const formatMoney = (amount: number, currency: string): string => {
  try {
    return new Intl.NumberFormat(currency === "GBP" ? "en-GB" : "en-US", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
};

const clinicLabel = (clinic: ClinicSupplyPerformance): string =>
  `Clinic ${clinic.clinic_id} (${clinic.country})`;

type KpiChartRow = {
  key: string;
  label: string;
  value: number;
  display: string;
};

const KpiBarChart = ({
  title,
  description,
  rows,
  emptyLabel,
}: {
  title: string;
  description: string;
  rows: KpiChartRow[];
  emptyLabel: string;
}) => {
  const maxValue = Math.max(0, ...rows.map((row) => row.value));
  return (
    <article className="kpi-panel">
      <h3>{title}</h3>
      <p className="kpi-panel__hint">{description}</p>
      {rows.length === 0 ? (
        <p className="field-hint">{emptyLabel}</p>
      ) : (
        <ul className="kpi-chart" aria-label={title}>
          {rows.map((row) => {
            const widthPercent =
              maxValue <= 0 ? 0 : Math.max(2, (row.value / maxValue) * 100);
            return (
              <li key={row.key} className="kpi-chart__row">
                <span className="kpi-chart__label">{row.label}</span>
                <span className="kpi-chart__track">
                  <span
                    className="kpi-chart__bar"
                    style={{ width: `${widthPercent}%` }}
                  />
                </span>
                <span className="kpi-chart__value">{row.display}</span>
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
};

const KpiTable = ({
  title,
  valueHeading,
  rows,
  emptyLabel,
}: {
  title: string;
  valueHeading: string;
  rows: KpiChartRow[];
  emptyLabel: string;
}) => (
  <article className="kpi-panel">
    <h3>{title}</h3>
    {rows.length === 0 ? (
      <p className="field-hint">{emptyLabel}</p>
    ) : (
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Clinic</th>
              <th scope="col">{valueHeading}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td>{row.display}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </article>
);

const toMonthInputValue = (monthStart: string): string => monthStart.slice(0, 7);

const monthInputToMonthStart = (yearMonth: string): string | undefined => {
  const match = /^(\d{4})-(\d{2})$/.exec(yearMonth);
  if (!match) {
    return undefined;
  }
  return `${match[1]}-${match[2]}-01`;
};

const reportErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError && error.status === 404) {
    return "No completed Monthly Clinic Supply Performance Report is available for this month yet.";
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  return "The report could not be loaded. Please try again.";
};

export const MonthlyClinicSupplyPerformanceDashboard = () => {
  const [report, setReport] =
    useState<MonthlyClinicSupplyPerformanceResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedMonth, setSelectedMonth] = useState("");

  const applyReport = (payload: MonthlyClinicSupplyPerformanceResponse) => {
    setReport(payload);
    setSelectedMonth(toMonthInputValue(payload.month_start));
    setLoadError(null);
  };

  const applyReportFailure = (error: unknown) => {
    setReport(null);
    setLoadError(reportErrorMessage(error));
  };

  useEffect(() => {
    let cancelled = false;

    const loadInitialReport = async () => {
      try {
        const payload = await getMonthlyClinicSupplyPerformance();
        if (cancelled) {
          return;
        }
        applyReport(payload);
      } catch (error) {
        if (cancelled) {
          return;
        }
        applyReportFailure(error);
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadInitialReport();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleMonthSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const monthStart = monthInputToMonthStart(selectedMonth);
    setIsLoading(true);
    setLoadError(null);
    void getMonthlyClinicSupplyPerformance(monthStart)
      .then((payload) => {
        applyReport(payload);
      })
      .catch((error: unknown) => {
        applyReportFailure(error);
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  const clinics = useMemo(() => report?.clinics ?? [], [report]);
  const usClinics = useMemo(
    () => clinics.filter((clinic) => clinic.country === "US"),
    [clinics],
  );
  const ukClinics = useMemo(
    () => clinics.filter((clinic) => clinic.country === "UK"),
    [clinics],
  );

  const usCostRows: KpiChartRow[] = usClinics.map((clinic) => ({
    key: `cost-us-${clinic.clinic_id}`,
    label: clinicLabel(clinic),
    value: clinic.total_supply_cost,
    display: formatMoney(clinic.total_supply_cost, "USD"),
  }));
  const ukCostRows: KpiChartRow[] = ukClinics.map((clinic) => ({
    key: `cost-uk-${clinic.clinic_id}`,
    label: clinicLabel(clinic),
    value: clinic.total_supply_cost,
    display: formatMoney(clinic.total_supply_cost, "GBP"),
  }));
  const consumptionRows: KpiChartRow[] = clinics.map((clinic) => ({
    key: `consumption-${clinic.clinic_id}`,
    label: clinicLabel(clinic),
    value: clinic.supply_consumption_count,
    display: String(clinic.supply_consumption_count),
  }));
  const stockoutRows: KpiChartRow[] = clinics.map((clinic) => ({
    key: `stockout-${clinic.clinic_id}`,
    label: clinicLabel(clinic),
    value: clinic.critical_stockout_count,
    display: String(clinic.critical_stockout_count),
  }));
  const expiryRows: KpiChartRow[] = clinics.map((clinic) => ({
    key: `expiry-${clinic.clinic_id}`,
    label: clinicLabel(clinic),
    value: clinic.expiry_risk_count,
    display: String(clinic.expiry_risk_count),
  }));

  const emptyLabel = "No clinic rows were published for this month.";

  return (
    <div className="reporting-dashboard">
      <form className="reporting-period" onSubmit={handleMonthSubmit}>
        <label htmlFor="report-month">Report month</label>
        <input
          id="report-month"
          type="month"
          value={selectedMonth}
          onChange={(event) => setSelectedMonth(event.target.value)}
        />
        <button type="submit" className="btn-primary">
          Show month
        </button>
      </form>

      {isLoading ? <p className="field-hint">Loading clinic supply figures…</p> : null}
      {loadError ? (
        <p className="form-error" role="alert">
          {loadError}
        </p>
      ) : null}

      {report ? (
        <>
          <p className="reporting-period__value">
            Month covered: <strong>{formatReportMonth(report.month_start)}</strong>{" "}
            (UTC calendar month starting {report.month_start})
          </p>

          <section className="kpi-section" aria-labelledby="kpi-supply-cost">
            <h2 id="kpi-supply-cost">Supply Cost per Clinic</h2>
            <p className="home-lede">
              Monthly medical-supply purchasing cost. US clinics are shown in USD
              and UK clinics in GBP. These totals are not added together.
            </p>
            <div className="kpi-grid">
              <KpiBarChart
                title="US clinics (USD)"
                description="Purchasing cost from inbound supply deliveries."
                rows={usCostRows}
                emptyLabel={emptyLabel}
              />
              <KpiBarChart
                title="UK clinics (GBP)"
                description="Purchasing cost from inbound supply deliveries."
                rows={ukCostRows}
                emptyLabel={emptyLabel}
              />
              <KpiTable
                title="US clinic cost table"
                valueHeading="Supply Cost per Clinic (USD)"
                rows={usCostRows}
                emptyLabel={emptyLabel}
              />
              <KpiTable
                title="UK clinic cost table"
                valueHeading="Supply Cost per Clinic (GBP)"
                rows={ukCostRows}
                emptyLabel={emptyLabel}
              />
            </div>
          </section>

          <section className="kpi-section" aria-labelledby="kpi-consumption">
            <h2 id="kpi-consumption">Supply Consumption Volume</h2>
            <p className="home-lede">
              Number of supply-consumption events recorded during the month, by
              clinic. Counts are event totals, not currency.
            </p>
            <div className="kpi-grid">
              <KpiBarChart
                title="Supply Consumption Volume by clinic"
                description="Count of outbound supply-consumption events."
                rows={consumptionRows}
                emptyLabel={emptyLabel}
              />
              <KpiTable
                title="Supply Consumption Volume table"
                valueHeading="Events"
                rows={consumptionRows}
                emptyLabel={emptyLabel}
              />
            </div>
          </section>

          <section className="kpi-section" aria-labelledby="kpi-stockout">
            <h2 id="kpi-stockout">Critical Stockout Frequency</h2>
            <p className="home-lede">
              Number of times a clinic fell below the minimum threshold for a
              supply during the month.
            </p>
            <div className="kpi-grid">
              <KpiBarChart
                title="Critical Stockout Frequency by clinic"
                description="Count of stock-threshold alerts."
                rows={stockoutRows}
                emptyLabel={emptyLabel}
              />
              <KpiTable
                title="Critical Stockout Frequency table"
                valueHeading="Events"
                rows={stockoutRows}
                emptyLabel={emptyLabel}
              />
            </div>
          </section>

          <section className="kpi-section" aria-labelledby="kpi-expiry">
            <h2 id="kpi-expiry">Expiry Risk Count</h2>
            <p className="home-lede">
              Number of supply batches flagged as approaching expiry during the
              month.
            </p>
            <div className="kpi-grid">
              <KpiBarChart
                title="Expiry Risk Count by clinic"
                description="Count of approaching-expiry flags."
                rows={expiryRows}
                emptyLabel={emptyLabel}
              />
              <KpiTable
                title="Expiry Risk Count table"
                valueHeading="Events"
                rows={expiryRows}
                emptyLabel={emptyLabel}
              />
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
};
