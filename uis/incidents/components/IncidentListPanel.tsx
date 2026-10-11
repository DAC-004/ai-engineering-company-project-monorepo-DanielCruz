"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";

import {
  ALLOWED_TRANSITIONS,
  BRANCH_LABELS,
  BRANCHES,
  CATEGORY_LABELS,
  ORIGIN_LABELS,
  ORIGINS,
  STATUS_LABELS,
  STATUSES,
} from "../constants";
import { listIncidents, updateIncidentStatus } from "../lib/api";
import type { Incident, IncidentListFilters, IncidentStatus } from "../types";

const emptyFilters: IncidentListFilters = {
  status: "",
  origin: "",
  branch: "",
};

export const IncidentListPanel = () => {
  const [filters, setFilters] = useState<IncidentListFilters>(emptyFilters);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [listError, setListError] = useState<string | null>(null);
  const [updateNotice, setUpdateNotice] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const loadIncidents = useCallback(async () => {
    setLoadState("loading");
    setListError(null);
    try {
      const records = await listIncidents(filters);
      setIncidents(records);
      setLoadState("ready");
    } catch {
      setListError(
        "The incident list could not be loaded. Check your connection and try again.",
      );
      setLoadState("error");
    }
  }, [filters]);

  useEffect(() => {
    void loadIncidents();
  }, [loadIncidents]);

  const handleStatusChange = async (
    incident: Incident,
    nextStatus: IncidentStatus,
  ) => {
    if (nextStatus === incident.status) {
      return;
    }

    const previous = incident.status;
    setUpdateNotice(null);
    setPendingId(incident.id);
    setIncidents((current) =>
      current.map((item) =>
        item.id === incident.id ? { ...item, status: nextStatus } : item,
      ),
    );

    try {
      const updated = await updateIncidentStatus(incident.id, nextStatus);
      setIncidents((current) =>
        current.map((item) => (item.id === incident.id ? updated : item)),
      );
    } catch (error) {
      setIncidents((current) =>
        current.map((item) =>
          item.id === incident.id ? { ...item, status: previous } : item,
        ),
      );
      setUpdateNotice(
        error instanceof ApiError && error.status < 500
          ? error.message
          : "The status update failed. The previous status was restored.",
      );
    } finally {
      setPendingId(null);
    }
  };

  return (
    <section className="incident-panel incident-panel--wide">
      <p className="eyebrow">Incident manager</p>
      <h1>Incidents</h1>
      <p className="home-lede">
        Filter registered incidents and update status when the lifecycle allows
        it.
      </p>

      <div className="incident-filters">
        <label className="field">
          <span>Status</span>
          <select
            value={filters.status}
            onChange={(event) =>
              setFilters((current) => ({ ...current, status: event.target.value }))
            }
          >
            <option value="">All statuses</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Origin</span>
          <select
            value={filters.origin}
            onChange={(event) =>
              setFilters((current) => ({ ...current, origin: event.target.value }))
            }
          >
            <option value="">All origins</option>
            {ORIGINS.map((origin) => (
              <option key={origin} value={origin}>
                {ORIGIN_LABELS[origin]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Branch</span>
          <select
            value={filters.branch}
            onChange={(event) =>
              setFilters((current) => ({ ...current, branch: event.target.value }))
            }
          >
            <option value="">All branches</option>
            {BRANCHES.map((branch) => (
              <option key={branch} value={branch}>
                {BRANCH_LABELS[branch]}
              </option>
            ))}
          </select>
        </label>
      </div>

      {updateNotice ? (
        <p className="form-error" role="alert">
          {updateNotice}
        </p>
      ) : null}

      {loadState === "loading" ? (
        <p className="auth-loading" role="status">
          Loading incidents…
        </p>
      ) : null}

      {loadState === "error" ? (
        <div className="incident-empty" role="alert">
          <p>{listError}</p>
          <button type="button" className="btn-secondary" onClick={() => void loadIncidents()}>
            Retry
          </button>
        </div>
      ) : null}

      {loadState === "ready" && incidents.length === 0 ? (
        <p className="incident-empty" role="status">
          No incidents match the current filters. Register an incident or clear
          a filter to see records.
        </p>
      ) : null}

      {loadState === "ready" && incidents.length > 0 ? (
        <div className="incident-table-wrap">
          <table className="incident-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Category</th>
                <th>Origin</th>
                <th>Branch</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((incident) => {
                const nextStatuses = ALLOWED_TRANSITIONS[incident.status];
                return (
                  <tr key={incident.id}>
                    <td>{incident.title}</td>
                    <td>{CATEGORY_LABELS[incident.category]}</td>
                    <td>{ORIGIN_LABELS[incident.origin]}</td>
                    <td>{BRANCH_LABELS[incident.branch]}</td>
                    <td>
                      <select
                        aria-label={`Status for ${incident.title}`}
                        value={incident.status}
                        disabled={pendingId === incident.id || nextStatuses.length === 0}
                        onChange={(event) =>
                          void handleStatusChange(
                            incident,
                            event.target.value as IncidentStatus,
                          )
                        }
                      >
                        <option value={incident.status}>
                          {STATUS_LABELS[incident.status]}
                        </option>
                        {nextStatuses.map((status) => (
                          <option key={status} value={status}>
                            {STATUS_LABELS[status]}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
};
