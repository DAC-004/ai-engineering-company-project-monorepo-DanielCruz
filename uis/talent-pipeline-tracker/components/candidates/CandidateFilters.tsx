"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { STAGE_OPTIONS, STATUS_OPTIONS } from "@/lib/labels";
import type { CandidateStage, CandidateStatus } from "@/types/candidate";

interface CandidateFiltersProps {
  onChange: (filters: {
    status: CandidateStatus | "";
    stage: CandidateStage | "";
    search: string;
    page: number;
  }) => void;
}

const SEARCH_COMMIT_DELAY_MS = 300;

export function CandidateFilters({ onChange }: CandidateFiltersProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlSearch = searchParams.get("search") ?? "";
  const [searchInput, setSearchInput] = useState(urlSearch);
  const [trackedUrlSearch, setTrackedUrlSearch] = useState(urlSearch);
  const searchCommitTimer = useRef<number | null>(null);

  const status = (searchParams.get("status") ?? "") as CandidateStatus | "";
  const stage = (searchParams.get("stage") ?? "") as CandidateStage | "";
  const search = searchParams.get("search") ?? "";
  const page = Number(searchParams.get("page") ?? "1");

  // Adopt a URL search change that did not come from the in-progress input.
  // History restoration clears the timer first, so Back/Forward wins over a
  // keystroke that has not been committed yet.
  if (urlSearch !== trackedUrlSearch) {
    setTrackedUrlSearch(urlSearch);
    if (searchCommitTimer.current === null) {
      setSearchInput(urlSearch);
    }
  }

  useEffect(() => {
    onChange({ status, stage, search, page });
  }, [status, stage, search, page, onChange]);

  useEffect(() => {
    const onPopState = () => {
      if (searchCommitTimer.current !== null) {
        window.clearTimeout(searchCommitTimer.current);
        searchCommitTimer.current = null;
      }

      const restoredSearch = new URLSearchParams(window.location.search).get("search") ?? "";
      setSearchInput(restoredSearch);
    };

    window.addEventListener("popstate", onPopState);
    return () => {
      window.removeEventListener("popstate", onPopState);
      if (searchCommitTimer.current !== null) {
        window.clearTimeout(searchCommitTimer.current);
        searchCommitTimer.current = null;
      }
    };
  }, []);

  function commitSearch(nextInput: string) {
    if (searchCommitTimer.current !== null) {
      window.clearTimeout(searchCommitTimer.current);
    }

    // This timer is owned by the search box only. It must not be re-armed when
    // page, status, or stage change searchParams, or pagination deletes itself.
    searchCommitTimer.current = window.setTimeout(() => {
      searchCommitTimer.current = null;
      const trimmedSearch = nextInput.trim();
      const params = new URLSearchParams(window.location.search);

      if (trimmedSearch === (params.get("search") ?? "")) {
        return;
      }

      if (trimmedSearch) {
        params.set("search", trimmedSearch);
      } else {
        params.delete("search");
      }

      params.delete("page");
      const nextQuery = params.toString();
      const currentQuery = window.location.search.replace(/^\?/, "");

      if (nextQuery !== currentQuery) {
        router.replace(nextQuery ? `/candidates?${nextQuery}` : "/candidates", {
          scroll: false,
        });
      }
    }, SEARCH_COMMIT_DELAY_MS);
  }

  function updateParam(key: "status" | "stage", value: string) {
    const params = new URLSearchParams(searchParams.toString());

    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }

    params.delete("page");
    const query = params.toString();
    router.replace(query ? `/candidates?${query}` : "/candidates", { scroll: false });
  }

  return (
    <div className="surface-card grid gap-5 p-4 md:grid-cols-3 md:p-5 lg:gap-6">
      <label className="flex flex-col gap-2">
        <span className="label-field">Search by name or email</span>
        <input
          type="search"
          value={searchInput}
          onChange={(event) => {
            const nextInput = event.target.value;
            setSearchInput(nextInput);
            commitSearch(nextInput);
          }}
          placeholder="Search candidates..."
          className="input-field"
        />
      </label>

      <label className="flex flex-col gap-2">
        <span className="label-field">Application Status</span>
        <select
          value={status}
          onChange={(event) => updateParam("status", event.target.value)}
          className="input-field"
        >
          <option value="">All statuses</option>
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
          onChange={(event) => updateParam("stage", event.target.value)}
          className="input-field"
        >
          <option value="">All stages</option>
          {STAGE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
