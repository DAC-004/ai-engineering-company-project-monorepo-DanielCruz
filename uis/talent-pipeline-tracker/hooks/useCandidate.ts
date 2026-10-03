"use client";

import { useEffect, useState } from "react";

import { getRecord } from "@/lib/api/records";
import type { Candidate } from "@/types/candidate";

interface UseCandidateResult {
  candidate: Candidate | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  setCandidate: (candidate: Candidate) => void;
}

export function useCandidate(id: string): UseCandidateResult {
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let isActive = true;

    async function fetchCandidate() {
      setLoading(true);
      setError(null);

      try {
        const response = await getRecord(id);

        if (isActive) {
          setCandidate(response);
        }
      } catch (fetchError) {
        if (isActive) {
          const message =
            fetchError instanceof Error
              ? fetchError.message
              : "Failed to load candidate.";
          setError(message);
          setCandidate(null);
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    void fetchCandidate();

    return () => {
      isActive = false;
    };
  }, [id, reloadToken]);

  return {
    candidate,
    loading,
    error,
    refetch: async () => {
      setReloadToken((current) => current + 1);
    },
    setCandidate,
  };
}
