import { apiFetch } from "@/lib/auth/api";

import type {
  Incident,
  IncidentCreatePayload,
  IncidentListFilters,
  IncidentSummary,
} from "../types";

const toQuery = (filters: IncidentListFilters): string => {
  const params = new URLSearchParams();
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.origin) {
    params.set("origin", filters.origin);
  }
  if (filters.branch) {
    params.set("branch", filters.branch);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const createIncident = (
  payload: IncidentCreatePayload,
): Promise<Incident> =>
  apiFetch<Incident>("/api/incidents", {
    auth: true,
    method: "POST",
    body: JSON.stringify(payload),
  });

export const listIncidents = (
  filters: IncidentListFilters,
): Promise<Incident[]> =>
  apiFetch<Incident[]>(`/api/incidents${toQuery(filters)}`, {
    auth: true,
    method: "GET",
  });

export const fetchIncidentSummary = (): Promise<IncidentSummary> =>
  apiFetch<IncidentSummary>("/api/incidents/summary", {
    auth: true,
    method: "GET",
  });

export const updateIncidentStatus = (
  incidentId: string,
  status: string,
): Promise<Incident> =>
  apiFetch<Incident>(`/api/incidents/${incidentId}/status`, {
    auth: true,
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
