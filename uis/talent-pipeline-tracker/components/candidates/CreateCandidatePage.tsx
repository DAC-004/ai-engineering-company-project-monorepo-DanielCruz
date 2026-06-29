"use client";

import { useRouter } from "next/navigation";

import { CandidateForm } from "@/components/candidates/CandidateForm";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { createRecord } from "@/lib/api/records";
import type { CandidateCreateInput } from "@/types/candidate";

export function CreateCandidatePage() {
  const router = useRouter();
  const { isSubmitting, error, success, run } = useAsyncAction();

  async function handleSubmit(values: CandidateCreateInput) {
    const created = await run(
      () => createRecord(values),
      "Candidate registered successfully.",
    );

    if (created) {
      router.push(`/candidates/${created.id}`);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-2xl font-semibold text-slate-900">
        Register New Candidate
      </h2>
      <p className="mt-2 text-sm text-slate-600">
        Add a clinical or operational applicant to HealthCore&apos;s People
        &amp; Workforce hiring pipeline.
      </p>

      <div className="mt-6">
        <CandidateForm
          submitLabel="Register candidate"
          submittingLabel="Registering..."
          isSubmitting={isSubmitting}
          error={error}
          success={success}
          onSubmit={handleSubmit}
        />
      </div>
    </section>
  );
}
