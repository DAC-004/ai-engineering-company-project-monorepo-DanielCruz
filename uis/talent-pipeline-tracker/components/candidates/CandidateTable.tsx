import Link from "next/link";

import { getStageLabel, getStatusLabel } from "@/lib/labels";
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
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              Full Name
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              Role Applied For
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              Status
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              Stage
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {candidates.map((candidate) => (
            <tr key={candidate.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <Link
                  href={`/candidates/${candidate.id}${suffix}`}
                  className="font-medium text-teal-800 hover:text-teal-900 hover:underline"
                >
                  {candidate.full_name}
                </Link>
              </td>
              <td className="px-4 py-3 text-slate-700">{candidate.position}</td>
              <td className="px-4 py-3">
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                  {getStatusLabel(candidate.status)}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-800">
                  {getStageLabel(candidate.stage)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
