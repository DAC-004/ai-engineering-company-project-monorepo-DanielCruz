import Link from "next/link";

import { StageBadge, StatusBadge } from "@/components/ui/PipelineBadge";
import { formatDate } from "@/lib/labels";
import type { Candidate } from "@/types/candidate";

interface CandidateDetailProps {
  candidate: Candidate;
  backHref: string;
}

export function CandidateDetail({ candidate, backHref }: CandidateDetailProps) {
  return (
    <section className="surface-card p-5 md:p-6 lg:p-8">
      <div className="mb-8 flex flex-col gap-4 border-b border-slate-100 pb-6 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">
            Candidate Profile
          </p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">
            {candidate.full_name}
          </h2>
          <p className="mt-2 text-base text-slate-600">{candidate.position}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge status={candidate.status} />
            <StageBadge stage={candidate.stage} />
          </div>
        </div>
        <Link
          href={`/candidates/${candidate.id}/edit`}
          className="btn-secondary shrink-0"
        >
          Edit Candidate
        </Link>
      </div>

      <dl className="grid gap-5 sm:grid-cols-2 md:gap-6 lg:grid-cols-3">
        <DetailItem label="Full Name" value={candidate.full_name} />
        <DetailItem label="Email" value={candidate.email} />
        <DetailItem label="Phone" value={candidate.phone} />
        <DetailItem label="Role Applied For" value={candidate.position} />
        <DetailItem
          label="Years of Experience"
          value={String(candidate.experience_years)}
        />
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
                className="font-medium text-teal-700 hover:text-teal-800 hover:underline"
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
                className="font-medium text-teal-700 hover:text-teal-800 hover:underline"
              >
                View CV
              </a>
            ) : (
              "Not provided"
            )
          }
        />
      </dl>

      <div className="mt-8 border-t border-slate-100 pt-6">
        <Link
          href={backHref}
          className="text-base font-semibold text-teal-700 hover:text-teal-800 hover:underline"
        >
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
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-2 text-base leading-7 text-slate-900">{value}</dd>
    </div>
  );
}
