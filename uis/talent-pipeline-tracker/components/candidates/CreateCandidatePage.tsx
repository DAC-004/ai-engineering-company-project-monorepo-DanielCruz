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
    <section className="surface-card p-5 md:p-6 lg:p-8">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">
        New Application
      </p>
      <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
        Register New Candidate
      </h2>
      <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600 md:text-lg">
        Add a clinical or operational applicant to HealthCore&apos;s People
        &amp; Workforce hiring pipeline.
      </p>

      <div className="mt-8">
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
