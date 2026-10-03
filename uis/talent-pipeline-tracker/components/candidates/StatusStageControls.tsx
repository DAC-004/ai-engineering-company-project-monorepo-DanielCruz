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
    <section className="surface-card p-5 md:p-6 lg:p-8">
      <h3 className="text-xl font-semibold tracking-tight text-hc-blue md:text-2xl">
        Application Status &amp; Hiring Stage
      </h3>
      <p className="mt-2 text-base leading-7 text-slate-600">
        Move this applicant through HealthCore&apos;s hiring pipeline.
      </p>

      <form
        onSubmit={handleSubmit}
        className="mt-6 grid gap-5 sm:grid-cols-2 md:gap-6"
      >
        <label className="flex flex-col gap-2">
          <span className="label-field">Application Status</span>
          <select
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as CandidateStatus)
            }
            disabled={isSubmitting}
            className="input-field disabled:opacity-60"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-2">
          <span className="label-field">Hiring Stage</span>
          <select
            value={stage}
            onChange={(event) => setStage(event.target.value as CandidateStage)}
            disabled={isSubmitting}
            className="input-field disabled:opacity-60"
          >
            {STAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <div className="sm:col-span-2">
          <button type="submit" disabled={isSubmitting} className="btn-primary">
            {isSubmitting ? "Saving..." : "Save status & stage"}
          </button>
        </div>
      </form>

      {success ? (
        <div className="mt-5">
          <SuccessMessage message={success} />
        </div>
      ) : null}

      {error ? (
        <div className="mt-5">
          <ErrorState message={error} />
        </div>
      ) : null}
    </section>
  );
}
