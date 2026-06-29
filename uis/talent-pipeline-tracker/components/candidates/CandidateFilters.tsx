"use client";

import { useEffect, useState } from "react";
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

export function CandidateFilters({ onChange }: CandidateFiltersProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [searchInput, setSearchInput] = useState(
    () => searchParams.get("search") ?? "",
  );

  const status = (searchParams.get("status") ?? "") as CandidateStatus | "";
  const stage = (searchParams.get("stage") ?? "") as CandidateStage | "";
  const search = searchParams.get("search") ?? "";
  const page = Number(searchParams.get("page") ?? "1");

  useEffect(() => {
    onChange({ status, stage, search, page });
  }, [status, stage, search, page, onChange]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      const params = new URLSearchParams(searchParams.toString());

      if (searchInput.trim()) {
        params.set("search", searchInput.trim());
      } else {
        params.delete("search");
      }

      params.delete("page");

      const nextQuery = params.toString();
      const currentQuery = searchParams.toString();

      if (nextQuery !== currentQuery) {
        router.replace(nextQuery ? `/?${nextQuery}` : "/", { scroll: false });
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [searchInput, router, searchParams]);

  function updateParam(key: "status" | "stage", value: string) {
    const params = new URLSearchParams(searchParams.toString());

    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }

    params.delete("page");
    const query = params.toString();
    router.replace(query ? `/?${query}` : "/", { scroll: false });
  }

  return (
    <div className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-3">
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium text-slate-700">Search by name or email</span>
        <input
          type="search"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="Search candidates..."
          className="rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium text-slate-700">Filter by status</span>
        <select
          value={status}
          onChange={(event) => updateParam("status", event.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium text-slate-700">Filter by stage</span>
        <select
          value={stage}
          onChange={(event) => updateParam("stage", event.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
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
