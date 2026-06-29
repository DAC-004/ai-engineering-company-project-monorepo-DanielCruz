"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { CandidateFilters } from "@/components/candidates/CandidateFilters";
import { CandidateTable } from "@/components/candidates/CandidateTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { useCandidates } from "@/hooks/useCandidates";
import type { CandidateStage, CandidateStatus } from "@/types/candidate";

const PAGE_LIMIT = 20;

export function CandidateListPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [filters, setFilters] = useState<{
    status: CandidateStatus | "";
    stage: CandidateStage | "";
    search: string;
    page: number;
  }>({
    status: "",
    stage: "",
    search: "",
    page: 1,
  });

  const handleFiltersChange = useCallback(
    (nextFilters: {
      status: CandidateStatus | "";
      stage: CandidateStage | "";
      search: string;
      page: number;
    }) => {
      setFilters(nextFilters);
    },
    [],
  );

  const { candidates, total, page, limit, loading, error, refetch } =
    useCandidates({
      status: filters.status,
      stage: filters.stage,
      search: filters.search,
      page: filters.page,
      limit: PAGE_LIMIT,
    });

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const queryString = searchParams.toString();

  const paginationLabel = useMemo(() => {
    if (total === 0) {
      return "No candidates found";
    }

    const start = (page - 1) * limit + 1;
    const end = Math.min(page * limit, total);
    return `Showing ${start}-${end} of ${total} candidates`;
  }, [total, page, limit]);

  function goToPage(nextPage: number) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", String(nextPage));
    router.replace(`/?${params.toString()}`, { scroll: false });
  }

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-2xl font-semibold text-slate-900">
          Clinical &amp; Operational Candidates
        </h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Track applicants for HealthCore&apos;s People &amp; Workforce hiring
          pipeline across US and UK clinic locations. Clinical roles currently
          take an average of 47 days to close.
        </p>
      </section>

      <CandidateFilters onChange={handleFiltersChange} />

      {loading ? <LoadingState message="Loading candidates..." /> : null}

      {!loading && error ? (
        <ErrorState message={error} onRetry={() => void refetch()} />
      ) : null}

      {!loading && !error && candidates.length === 0 ? (
        <EmptyState
          title="No candidates match your filters"
          description="Try adjusting the status, stage, or search terms."
        />
      ) : null}

      {!loading && !error && candidates.length > 0 ? (
        <>
          <CandidateTable candidates={candidates} queryString={queryString} />
          <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-600">{paginationLabel}</p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => goToPage(page - 1)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 enabled:hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-slate-600">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => goToPage(page + 1)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 enabled:hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
