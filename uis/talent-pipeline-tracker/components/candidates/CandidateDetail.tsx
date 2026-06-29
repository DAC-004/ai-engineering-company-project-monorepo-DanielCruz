import Link from "next/link";

import { formatDate, getStageLabel, getStatusLabel } from "@/lib/labels";
import type { Candidate } from "@/types/candidate";

interface CandidateDetailProps {
  candidate: Candidate;
  backHref: string;
}

export function CandidateDetail({ candidate, backHref }: CandidateDetailProps) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="mb-6 flex flex-col gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-wide text-teal-700">
            Candidate Profile
          </p>
          <h2 className="mt-1 text-2xl font-semibold text-slate-900">
            {candidate.full_name}
          </h2>
          <p className="mt-1 text-sm text-slate-600">{candidate.position}</p>
        </div>
        <Link
          href={`/candidates/${candidate.id}/edit`}
          className="inline-flex items-center justify-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Edit Candidate
        </Link>
      </div>

      <dl className="grid gap-4 sm:grid-cols-2">
        <DetailItem label="Full Name" value={candidate.full_name} />
        <DetailItem label="Email" value={candidate.email} />
        <DetailItem label="Phone" value={candidate.phone} />
        <DetailItem label="Role Applied For" value={candidate.position} />
        <DetailItem
          label="Years of Experience"
          value={String(candidate.experience_years)}
        />
        <DetailItem label="Status" value={getStatusLabel(candidate.status)} />
        <DetailItem label="Stage" value={getStageLabel(candidate.stage)} />
        <DetailItem
          label="Application Date"
          value={formatDate(candidate.applied_at)}
        />
        <DetailItem
          label="LinkedIn"
          value={
            candidate.linkedin_url ? (
              <a
                href={candidate.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-teal-800 hover:underline"
              >
                View profile
              </a>
            ) : (
              "Not provided"
            )
          }
        />
        <DetailItem
          label="CV"
          value={
            candidate.cv_url ? (
              <a
                href={candidate.cv_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-teal-800 hover:underline"
              >
                View CV
              </a>
            ) : (
              "Not provided"
            )
          }
        />
      </dl>

      <div className="mt-6">
        <Link href={backHref} className="text-sm font-medium text-teal-800 hover:underline">
          ← Back to pipeline
        </Link>
      </div>
    </section>
  );
}

function DetailItem({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-slate-800">{value}</dd>
    </div>
  );
}
