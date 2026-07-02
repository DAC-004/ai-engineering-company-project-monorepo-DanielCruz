import Link from "next/link";

import { StageBadge, StatusBadge } from "@/components/ui/PipelineBadge";
import { formatDate, formatPosition } from "@/lib/labels";
import type { Candidate } from "@/types/candidate";

interface CandidateTableProps {
  candidates: Candidate[];
  queryString?: string;
}

export function CandidateTable({
  candidates,
  queryString = "",
}: CandidateTableProps) {
  const suffix = queryString ? `?${queryString}` : "";

  return (
    <>
      {/* Desktop table */}
      <div className="surface-card hidden overflow-hidden md:block">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                Candidate
              </th>
              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                Role Applied For
              </th>
              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                Status
              </th>
              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                Stage
              </th>
              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                Applied
              </th>
              <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-600">
                Action
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {candidates.map((candidate) => (
              <tr
                key={candidate.id}
                className="transition-colors hover:bg-slate-50"
              >
                <td className="px-6 py-5">
                  <div>
                    <p className="text-base font-semibold text-slate-900">
                      {candidate.full_name}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {candidate.email}
                    </p>
                  </div>
                </td>
                <td className="px-6 py-5 text-base text-slate-700">
                  {formatPosition(candidate.position)}
                </td>
                <td className="px-6 py-5">
                  <StatusBadge status={candidate.status} />
                </td>
                <td className="px-6 py-5">
                  <StageBadge stage={candidate.stage} />
                </td>
                <td className="px-6 py-5 text-sm text-slate-600">
                  {formatDate(candidate.applied_at)}
                </td>
                <td className="px-6 py-5 text-right">
                  <Link
                    href={`/candidates/${candidate.id}${suffix}`}
                    className="link-accent text-sm"
                  >
                    View details
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="space-y-3 md:hidden">
        {candidates.map((candidate) => (
          <article
            key={candidate.id}
            className="surface-card p-4 shadow-sm"
          >
            <div className="flex flex-col gap-3">
              <div>
                <h3 className="text-base font-semibold text-slate-900">
                  {candidate.full_name}
                </h3>
                <p className="mt-1 text-sm text-slate-500">{candidate.email}</p>
              </div>
              <p className="text-sm text-slate-700">
                {formatPosition(candidate.position)}
              </p>
              <div className="flex flex-wrap gap-2">
                <StatusBadge status={candidate.status} />
                <StageBadge stage={candidate.stage} />
              </div>
              <p className="text-sm text-slate-500">
                Applied {formatDate(candidate.applied_at)}
              </p>
              <Link
                href={`/candidates/${candidate.id}${suffix}`}
                className="btn-secondary w-full"
              >
                View details
              </Link>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
