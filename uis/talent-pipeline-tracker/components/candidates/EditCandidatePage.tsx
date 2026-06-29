"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  CandidateForm,
  candidateToFormValues,
} from "@/components/candidates/CandidateForm";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { useCandidate } from "@/hooks/useCandidate";
import { updateRecord } from "@/lib/api/records";
import type { CandidateCreateInput } from "@/types/candidate";

interface EditCandidatePageProps {
  candidateId: string;
}

export function EditCandidatePage({ candidateId }: EditCandidatePageProps) {
  const router = useRouter();
  const { candidate, loading, error, refetch } = useCandidate(candidateId);
  const { isSubmitting, error: submitError, success, run } = useAsyncAction();

  async function handleSubmit(values: CandidateCreateInput) {
    const updated = await run(
      () => updateRecord(candidateId, values),
      "Candidate updated successfully.",
    );

    if (updated) {
      router.push(`/candidates/${candidateId}`);
    }
  }

  if (loading) {
    return <LoadingState message="Loading candidate..." />;
  }

  if (error || !candidate) {
    return (
      <div className="space-y-5">
        <ErrorState
          message={error ?? "Candidate not found."}
          onRetry={() => void refetch()}
        />
        <Link
          href="/"
          className="link-accent text-base"
        >
          ← Back to pipeline
        </Link>
      </div>
    );
  }

  const initialValues = candidateToFormValues(candidate);

  return (
    <section className="surface-card p-5 md:p-6 lg:p-8">
      <p className="eyebrow">Edit Application</p>
      <h2 className="mt-2 text-3xl font-bold tracking-tight text-hc-blue md:text-4xl">
        Update Candidate Record
      </h2>
      <p className="mt-4 text-base leading-7 text-slate-600 md:text-lg">
        Update applicant details for {candidate.full_name}.
      </p>

      <div className="mt-8">
        <CandidateForm
          initialValues={initialValues}
          submitLabel="Save changes"
          submittingLabel="Saving..."
          isSubmitting={isSubmitting}
          error={submitError}
          success={success}
          onSubmit={handleSubmit}
        />
      </div>
    </section>
  );
}
