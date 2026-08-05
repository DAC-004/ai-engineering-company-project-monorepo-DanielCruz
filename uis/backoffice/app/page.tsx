import { MetricCard } from "@/components/ui/MetricCard";
import { SectionCard } from "@/components/ui/SectionCard";
import { sampleAppointments, sampleCareRequests, sampleClinics } from "../../../src/data/sample";
import { getCareRequestSummary } from "../../../src/types/models";
import { generateOperationalReports } from "../../../src/utils/transformations";

const reports = generateOperationalReports(sampleCareRequests, sampleAppointments, sampleClinics);
const visibleSummaries = sampleCareRequests.map(getCareRequestSummary);

export default function BackofficeHome() {
  return (
    <main className="bo-shell py-8 lg:py-10">
      <div className="rounded-4xl border border-(--bo-line) bg-[linear-gradient(135deg,#10303b_0%,#154d58_58%,#1d6975_100%)] px-6 py-8 text-white shadow-[0_24px_80px_-36px_rgba(16,48,59,0.7)] lg:px-8 lg:py-10">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-100">
          Internal Operations Workspace
        </p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight lg:text-5xl">
          HealthCore Backoffice
        </h1>
        <p className="mt-4 max-w-3xl text-base leading-relaxed text-cyan-50 lg:text-lg">
          This internal entry view imports the authoritative Milestone 2 TypeScript utilities from
          src/ and renders their output directly for operations staff. It is separate from the
          public website and preserves the original business logic in one source location.
        </p>
      </div>

      <section className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Care requests"
          value={sampleCareRequests.length}
          detail="Input array imported from src/data/sample.ts"
        />
        <MetricCard
          label="Appointments"
          value={sampleAppointments.length}
          detail="Input array imported from src/data/sample.ts"
        />
        <MetricCard
          label="US requests"
          value={reports.careRequests.byMarketCountry.US ?? 0}
          detail="Computed by generateOperationalReports from src/utils/transformations.ts"
        />
        <MetricCard
          label="Average days until visit"
          value={reports.careRequests.averageDaysUntilPreferredDate ?? "n/a"}
          detail="Rounded output from the Milestone 2 reporting logic"
        />
      </section>

      <section className="mt-8 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <SectionCard
          title="Visible Milestone 2 Output"
          subtitle="These care-request summaries are rendered from getCareRequestSummary in src/types/models.ts."
        >
          <ul className="space-y-3">
            {visibleSummaries.map((summary) => (
              <li
                key={summary}
                className="rounded-2xl border border-(--bo-line) bg-(--bo-accent-soft)/45 px-4 py-3 text-sm font-medium text-(--bo-ink) lg:text-base"
              >
                {summary}
              </li>
            ))}
          </ul>
        </SectionCard>

        <SectionCard
          title="Operational report output"
          subtitle="Rendered JSON comes directly from generateOperationalReports(sampleCareRequests, sampleAppointments, sampleClinics)."
        >
          <pre className="overflow-x-auto rounded-2xl bg-[#0d1c22] p-4 text-xs leading-6 text-cyan-50 lg:text-sm">
            {JSON.stringify(reports, null, 2)}
          </pre>
        </SectionCard>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <SectionCard
          title="Care request status distribution"
          subtitle="Status counts are computed from the authoritative Milestone 2 report object."
        >
          <dl className="grid gap-3 sm:grid-cols-2">
            {Object.entries(reports.careRequests.byStatus).map(([status, count]) => (
              <div key={status} className="rounded-2xl border border-(--bo-line) bg-white px-4 py-4">
                <dt className="text-sm font-semibold uppercase tracking-[0.14em] text-(--bo-muted)">
                  {status}
                </dt>
                <dd className="mt-2 text-2xl font-bold text-(--bo-ink)">{count}</dd>
              </div>
            ))}
          </dl>
        </SectionCard>

        <SectionCard
          title="Clinic activity overview"
          subtitle="Appointment counts by clinic are derived from generateAppointmentReports inside the same Milestone 2 pipeline."
        >
          <dl className="space-y-3">
            {Object.entries(reports.appointments.byClinicName).map(([clinicName, count]) => (
              <div key={clinicName} className="flex items-center justify-between rounded-2xl border border-(--bo-line) bg-white px-4 py-4">
                <dt className="text-sm font-medium text-(--bo-ink) lg:text-base">{clinicName}</dt>
                <dd className="rounded-full bg-(--bo-accent-soft) px-3 py-1 text-sm font-semibold text-(--bo-accent)">
                  {count}
                </dd>
              </div>
            ))}
          </dl>
        </SectionCard>
      </section>
    </main>
  );
}
