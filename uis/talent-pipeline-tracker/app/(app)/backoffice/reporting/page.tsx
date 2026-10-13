import { MonthlyClinicSupplyPerformanceDashboard } from "@/components/reporting/MonthlyClinicSupplyPerformanceDashboard";

export default function MonthlyClinicSupplyPerformancePage() {
  return (
    <section className="home-panel inventory-panel">
      <p className="eyebrow">Monthly Clinic Supply Performance Report</p>
      <h1>Clinic supply performance</h1>
      <p className="home-lede">
        Prepared for Dr. Okonkwo and Claire Whitfield. Figures are monthly
        clinic totals for HealthCore&apos;s 12 US and UK clinics. US costs stay
        in USD and UK costs stay in GBP. Currencies are never combined.
      </p>
      <MonthlyClinicSupplyPerformanceDashboard />
    </section>
  );
}
