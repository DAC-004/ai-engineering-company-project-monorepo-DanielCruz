import type { CandidateStage, CandidateStatus } from "@/types/candidate";

import { getStageLabel, getStatusLabel } from "@/lib/labels";

const STATUS_STYLES: Record<CandidateStatus, string> = {
  received: "bg-slate-100 text-slate-700 ring-slate-200",
  in_progress: "bg-sky-50 text-sky-800 ring-sky-200",
  selected: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  discarded: "bg-rose-50 text-rose-800 ring-rose-200",
};

const STAGE_STYLES: Record<CandidateStage, string> = {
  pending: "bg-amber-50 text-amber-900 ring-amber-200",
  review: "bg-teal-50 text-teal-800 ring-teal-200",
  personal_interview: "bg-cyan-50 text-cyan-900 ring-cyan-200",
  technical_interview: "bg-indigo-50 text-indigo-900 ring-indigo-200",
  offer_presented: "bg-violet-50 text-violet-900 ring-violet-200",
};

interface PipelineBadgeProps {
  label: string;
  className: string;
}

function PipelineBadge({ label, className }: PipelineBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset md:text-sm ${className}`}
    >
      {label}
    </span>
  );
}

export function StatusBadge({ status }: { status: CandidateStatus }) {
  return (
    <PipelineBadge
      label={getStatusLabel(status)}
      className={STATUS_STYLES[status]}
    />
  );
}

export function StageBadge({ stage }: { stage: CandidateStage }) {
  return (
    <PipelineBadge
      label={getStageLabel(stage)}
      className={STAGE_STYLES[stage]}
    />
  );
}
