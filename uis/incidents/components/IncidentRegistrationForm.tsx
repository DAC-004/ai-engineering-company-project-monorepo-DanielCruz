"use client";

import { FormEvent, useState } from "react";

import { ApiError, type FieldErrors } from "@/lib/auth/types";

import {
  BRANCH_LABELS,
  BRANCHES,
  CATEGORIES,
  CATEGORY_LABELS,
  DEFAULT_BRANCH,
  DEFAULT_CREATE_STATUS,
  ORIGIN_LABELS,
  ORIGINS,
  STATUS_LABELS,
  STATUSES,
} from "../constants";
import { createIncident } from "../lib/api";
import type { IncidentCreatePayload } from "../types";

const emptyFields: IncidentCreatePayload = {
  title: "",
  description: "",
  category: "patient_experience",
  status: DEFAULT_CREATE_STATUS,
  origin: "customer",
  branch: DEFAULT_BRANCH,
};

const requiredMessage = (label: string) => `${label} is required.`;

export const IncidentRegistrationForm = () => {
  const [fields, setFields] = useState<IncidentCreatePayload>(emptyFields);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const updateField = <K extends keyof IncidentCreatePayload>(
    name: K,
    value: IncidentCreatePayload[K],
  ) => {
    setFields((current) => ({ ...current, [name]: value }));
  };

  const validateClient = (): FieldErrors => {
    const errors: FieldErrors = {};
    if (!fields.title.trim()) {
      errors.title = requiredMessage("Title");
    }
    if (!fields.description.trim()) {
      errors.description = requiredMessage("Description");
    }
    if (!fields.category) {
      errors.category = requiredMessage("Category");
    }
    if (!fields.status) {
      errors.status = requiredMessage("Status");
    }
    if (!fields.origin) {
      errors.origin = requiredMessage("Origin");
    }
    if (!fields.branch) {
      errors.branch = requiredMessage("Branch");
    }
    return errors;
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setSuccessMessage(null);

    const clientErrors = validateClient();
    if (Object.keys(clientErrors).length > 0) {
      setFieldErrors(clientErrors);
      return;
    }

    setFieldErrors({});
    setIsSubmitting(true);

    try {
      await createIncident({
        ...fields,
        title: fields.title.trim(),
        description: fields.description,
      });
      setFields(emptyFields);
      setSuccessMessage("Incident registered. It is now available in the incident list.");
    } catch (error) {
      if (error instanceof ApiError) {
        if (Object.keys(error.fieldErrors).length > 0) {
          setFieldErrors(error.fieldErrors);
        }
        setFormError(
          error.status >= 500
            ? "The service could not save this incident. Please try again."
            : error.message,
        );
      } else {
        setFormError(
          "Unable to register the incident. Check your connection and try again.",
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const branchHighlighted = fields.origin === "branch";

  return (
    <section className="incident-panel">
      <p className="eyebrow">Incident manager</p>
      <h1>Register an incident</h1>
      <p className="home-lede">
        Record a HealthCore incident for a clinic, a customer report, or an
        internal finding. Generated identifiers and timestamps are assigned
        automatically.
      </p>

      <div className="phi-warning" role="alert">
        <strong>Do not enter identifying patient data.</strong>
        Title and description must not include a patient name, date of birth,
        medical record number, contact details, or any other identifying
        information. If a patient must be referenced, use only an opaque
        internal identifier.
      </div>

      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="incident-title">Title</label>
          <input
            id="incident-title"
            name="title"
            type="text"
            required
            value={fields.title}
            disabled={isSubmitting}
            onChange={(event) => updateField("title", event.target.value)}
            aria-invalid={Boolean(fieldErrors.title)}
          />
          {fieldErrors.title ? (
            <p className="field-error" role="alert">
              {fieldErrors.title}
            </p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="incident-description">Description</label>
          <textarea
            id="incident-description"
            name="description"
            required
            rows={5}
            value={fields.description}
            disabled={isSubmitting}
            onChange={(event) => updateField("description", event.target.value)}
            aria-invalid={Boolean(fieldErrors.description)}
          />
          {fieldErrors.description ? (
            <p className="field-error" role="alert">
              {fieldErrors.description}
            </p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="incident-category">Category</label>
          <select
            id="incident-category"
            name="category"
            required
            value={fields.category}
            disabled={isSubmitting}
            onChange={(event) =>
              updateField("category", event.target.value as IncidentCreatePayload["category"])
            }
            aria-invalid={Boolean(fieldErrors.category)}
          >
            {CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {CATEGORY_LABELS[category]}
              </option>
            ))}
          </select>
          {fieldErrors.category ? (
            <p className="field-error" role="alert">
              {fieldErrors.category}
            </p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="incident-status">Status</label>
          <select
            id="incident-status"
            name="status"
            required
            value={fields.status}
            disabled={isSubmitting}
            onChange={(event) =>
              updateField("status", event.target.value as IncidentCreatePayload["status"])
            }
            aria-invalid={Boolean(fieldErrors.status)}
          >
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </select>
          {fieldErrors.status ? (
            <p className="field-error" role="alert">
              {fieldErrors.status}
            </p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="incident-origin">Origin</label>
          <select
            id="incident-origin"
            name="origin"
            required
            value={fields.origin}
            disabled={isSubmitting}
            onChange={(event) =>
              updateField("origin", event.target.value as IncidentCreatePayload["origin"])
            }
            aria-invalid={Boolean(fieldErrors.origin)}
          >
            {ORIGINS.map((origin) => (
              <option key={origin} value={origin}>
                {ORIGIN_LABELS[origin]}
              </option>
            ))}
          </select>
          {fieldErrors.origin ? (
            <p className="field-error" role="alert">
              {fieldErrors.origin}
            </p>
          ) : null}
        </div>

        <div
          className={
            branchHighlighted ? "field field--branch-highlight" : "field"
          }
        >
          <label htmlFor="incident-branch">Branch</label>
          <select
            id="incident-branch"
            name="branch"
            required
            value={fields.branch}
            disabled={isSubmitting}
            onChange={(event) =>
              updateField("branch", event.target.value as IncidentCreatePayload["branch"])
            }
            aria-invalid={Boolean(fieldErrors.branch)}
          >
            {BRANCHES.map((branch) => (
              <option key={branch} value={branch}>
                {BRANCH_LABELS[branch]}
              </option>
            ))}
          </select>
          {fieldErrors.branch ? (
            <p className="field-error" role="alert">
              {fieldErrors.branch}
            </p>
          ) : null}
        </div>

        {formError ? (
          <p className="form-error" role="alert">
            {formError}
          </p>
        ) : null}
        {successMessage ? (
          <p className="form-success" role="status">
            {successMessage}
          </p>
        ) : null}

        <button type="submit" className="btn-primary" disabled={isSubmitting}>
          {isSubmitting ? "Saving incident…" : "Register incident"}
        </button>
      </form>
    </section>
  );
};
