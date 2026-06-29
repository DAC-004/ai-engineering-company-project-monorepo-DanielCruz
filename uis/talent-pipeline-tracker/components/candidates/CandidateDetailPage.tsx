"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { CandidateDetail } from "@/components/candidates/CandidateDetail";
import { NotesSection } from "@/components/candidates/NotesSection";
import { StatusStageControls } from "@/components/candidates/StatusStageControls";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { useCandidate } from "@/hooks/useCandidate";

interface CandidateDetailPageProps {
  candidateId: string;
}

export function CandidateDetailPage({ candidateId }: CandidateDetailPageProps) {
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const backHref = queryString ? `/?${queryString}` : "/";

  const { candidate, loading, error, refetch, setCandidate } =
    useCandidate(candidateId);

  if (loading) {
    return <LoadingState message="Loading candidate profile..." />;
  }

  if (error || !candidate) {
    return (
      <div className="space-y-4">
        <ErrorState
          message={error ?? "Candidate not found."}
          onRetry={() => void refetch()}
        />
        <Link href={backHref} className="text-sm font-medium text-teal-800 hover:underline">
          ← Back to pipeline
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <CandidateDetail candidate={candidate} backHref={backHref} />
      <StatusStageControls candidate={candidate} onUpdated={setCandidate} />
      <NotesSection recordId={candidate.id} />
    </div>
  );
}
