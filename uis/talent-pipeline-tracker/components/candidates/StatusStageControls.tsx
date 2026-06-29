"use client";

import { useState } from "react";

import { ErrorState } from "@/components/ui/ErrorState";
import { SuccessMessage } from "@/components/ui/SuccessMessage";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { patchRecord } from "@/lib/api/records";
import { STAGE_OPTIONS, STATUS_OPTIONS } from "@/lib/labels";
import type { Candidate, CandidateStage, CandidateStatus } from "@/types/candidate";

interface StatusStageControlsProps {
  candidate: Candidate;
  onUpdated: (candidate: Candidate) => void;
}

export function StatusStageControls({
  candidate,
  onUpdated,
}: StatusStageControlsProps) {
  const [status, setStatus] = useState<CandidateStatus>(candidate.status);
  const [stage, setStage] = useState<CandidateStage>(candidate.stage);
  const { isSubmitting, error, success, run } = useAsyncAction();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const updated = await run(
      () => patchRecord(candidate.id, { status, stage }),
      "Status and stage updated successfully.",
    );

    if (updated) {
      onUpdated(updated);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h3 className="text-lg font-semibold text-slate-900">
        Update Pipeline Status
      </h3>
      <p className="mt-1 text-sm text-slate-600">
        Move this applicant through HealthCore&apos;s hiring pipeline.
      </p>

      <form onSubmit={handleSubmit} className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-700">Status</span>
          <select
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as CandidateStatus)
            }
            disabled={isSubmitting}
            className="rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100 disabled:opacity-60"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-700">Stage</span>
          <select
            value={stage}
            onChange={(event) => setStage(event.target.value as CandidateStage)}
            disabled={isSubmitting}
            className="rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100 disabled:opacity-60"
          >
            {STAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Saving..." : "Save status & stage"}
          </button>
        </div>
      </form>

      {success ? (
        <div className="mt-4">
          <SuccessMessage message={success} />
        </div>
      ) : null}

      {error ? (
        <div className="mt-4">
          <ErrorState message={error} />
        </div>
      ) : null}
    </section>
  );
}
