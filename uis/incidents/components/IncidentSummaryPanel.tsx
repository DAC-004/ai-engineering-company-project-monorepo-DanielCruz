"use client";

import { useCallback, useEffect, useState } from "react";

import {
  BRANCH_LABELS,
  BRANCHES,
  CATEGORIES,
  CATEGORY_LABELS,
  ORIGIN_LABELS,
  ORIGINS,
  STATUS_LABELS,
  STATUSES,
} from "../constants";
import { fetchIncidentSummary } from "../lib/api";
import type { IncidentSummary } from "../types";

const emptySummary = (): IncidentSummary => ({
  by_status: {},
  by_category: {},
  by_origin: {},
  by_branch: {},
});

type MetricGroupProps = {
  heading: string;
  entries: Array<{ key: string; label: string; count: number }>;
};

const MetricGroup = ({ heading, entries }: MetricGroupProps) => (
  <article className="summary-card">
    <h2>{heading}</h2>
    <ul>
      {entries.map((entry) => (
        <li key={entry.key}>
          <span>{entry.label}</span>
          <strong>{entry.count}</strong>
        </li>
      ))}
    </ul>
  </article>
);

export const IncidentSummaryPanel = () => {
  const [summary, setSummary] = useState<IncidentSummary>(emptySummary);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">(
    "loading",
  );

  const loadSummary = useCallback(async () => {
    setLoadState("loading");
    try {
      const data = await fetchIncidentSummary();
      setSummary(data);
      setLoadState("ready");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  return (
    <section className="incident-panel incident-panel--wide">
      <p className="eyebrow">Incident manager</p>
      <h1>Summary</h1>
      <p className="home-lede">
        Network totals by status, category, origin, and branch.
      </p>

      {loadState === "loading" ? (
        <p className="auth-loading" role="status">
          Loading summary…
        </p>
      ) : null}

      {loadState === "error" ? (
        <div className="incident-empty" role="alert">
          <p>
            Summary metrics could not be loaded. The rest of the workspace is
            still available.
          </p>
          <button type="button" className="btn-secondary" onClick={() => void loadSummary()}>
            Retry
          </button>
        </div>
      ) : null}

      {loadState === "ready" ? (
        <div className="summary-grid">
          <MetricGroup
            heading="By status"
            entries={STATUSES.map((status) => ({
              key: status,
              label: STATUS_LABELS[status],
              count: summary.by_status[status] ?? 0,
            }))}
          />
          <MetricGroup
            heading="By category"
            entries={CATEGORIES.map((category) => ({
              key: category,
              label: CATEGORY_LABELS[category],
              count: summary.by_category[category] ?? 0,
            }))}
          />
          <MetricGroup
            heading="By origin"
            entries={ORIGINS.map((origin) => ({
              key: origin,
              label: ORIGIN_LABELS[origin],
              count: summary.by_origin[origin] ?? 0,
            }))}
          />
          <MetricGroup
            heading="By branch"
            entries={BRANCHES.map((branch) => ({
              key: branch,
              label: BRANCH_LABELS[branch],
              count: summary.by_branch[branch] ?? 0,
            }))}
          />
        </div>
      ) : null}
    </section>
  );
};
