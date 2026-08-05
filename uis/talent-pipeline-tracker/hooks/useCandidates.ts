"use client";

import { useEffect, useState } from "react";

import { getRecords, type ListRecordsParams } from "@/lib/api/records";
import type { PaginatedCandidatesResponse } from "@/types/api";
import type { Candidate } from "@/types/candidate";

interface UseCandidatesResult {
  candidates: Candidate[];
  total: number;
  page: number;
  limit: number;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useCandidates(params: ListRecordsParams): UseCandidatesResult {
  const [data, setData] = useState<PaginatedCandidatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const status = params.status ?? "";
  const stage = params.stage ?? "";
  const search = params.search ?? "";
  const page = params.page ?? 1;
  const limit = params.limit ?? 20;

  useEffect(() => {
    let isActive = true;

    async function fetchCandidates() {
      setLoading(true);
      setError(null);

      try {
        const response = await getRecords({
          status,
          stage,
          search,
          page,
          limit,
        });

        if (isActive) {
          setData(response);
        }
      } catch (fetchError) {
        if (isActive) {
          const message =
            fetchError instanceof Error
              ? fetchError.message
              : "Failed to load candidates.";
          setError(message);
          setData(null);
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    void fetchCandidates();

    return () => {
      isActive = false;
    };
  }, [status, stage, search, page, limit, reloadToken]);

  return {
    candidates: data?.data ?? [],
    total: data?.total ?? 0,
    page: data?.page ?? page,
    limit: data?.limit ?? limit,
    loading,
    error,
    refetch: async () => {
      setReloadToken((current) => current + 1);
    },
  };
}
