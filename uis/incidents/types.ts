import type {
  BRANCHES,
  CATEGORIES,
  ORIGINS,
  STATUSES,
} from "./constants";

export type IncidentCategory = (typeof CATEGORIES)[number];
export type IncidentStatus = (typeof STATUSES)[number];
export type IncidentOrigin = (typeof ORIGINS)[number];
export type IncidentBranch = (typeof BRANCHES)[number];

export type Incident = {
  id: string;
  title: string;
  description: string;
  category: IncidentCategory;
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: IncidentBranch;
  created_at: string;
  updated_at: string;
};

export type IncidentCreatePayload = {
  title: string;
  description: string;
  category: IncidentCategory;
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: IncidentBranch;
};

export type IncidentSummary = {
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  by_origin: Record<string, number>;
  by_branch: Record<string, number>;
};

export type IncidentListFilters = {
  status: string;
  origin: string;
  branch: string;
};
