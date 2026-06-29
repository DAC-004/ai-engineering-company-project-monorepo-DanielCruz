"use client";

import { useState } from "react";

import { ErrorState } from "@/components/ui/ErrorState";
import { SuccessMessage } from "@/components/ui/SuccessMessage";
import type { CandidateCreateInput } from "@/types/candidate";

export interface CandidateFormValues {
  full_name: string;
  email: string;
  phone: string;
  position: string;
  experience_years: string;
  linkedin_url: string;
  cv_url: string;
}

interface CandidateFormProps {
  initialValues?: Partial<CandidateFormValues>;
  submitLabel: string;
  submittingLabel: string;
  isSubmitting: boolean;
  error: string | null;
  success: string | null;
  onSubmit: (values: CandidateCreateInput) => Promise<void>;
}

const EMPTY_VALUES: CandidateFormValues = {
  full_name: "",
  email: "",
  phone: "",
  position: "",
  experience_years: "",
  linkedin_url: "",
  cv_url: "",
};

export function CandidateForm({
  initialValues,
  submitLabel,
  submittingLabel,
  isSubmitting,
  error,
  success,
  onSubmit,
}: CandidateFormProps) {
  const [values, setValues] = useState<CandidateFormValues>({
    ...EMPTY_VALUES,
    ...initialValues,
  });
  const [validationError, setValidationError] = useState<string | null>(null);

  function updateField(
    field: keyof CandidateFormValues,
    value: string,
  ) {
    setValues((current) => ({ ...current, [field]: value }));
    setValidationError(null);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const errors = validateCandidateForm(values);
    const firstError = Object.values(errors)[0];

    if (firstError) {
      setValidationError(firstError);
      return;
    }

    await onSubmit({
      full_name: values.full_name.trim(),
      email: values.email.trim(),
      phone: values.phone.trim(),
      position: values.position.trim(),
      experience_years: Number(values.experience_years),
      linkedin_url: values.linkedin_url.trim() || null,
      cv_url: values.cv_url.trim() || null,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          label="Full Name"
          name="full_name"
          value={values.full_name}
          onChange={(value) => updateField("full_name", value)}
          required
        />
        <FormField
          label="Email"
          name="email"
          type="email"
          value={values.email}
          onChange={(value) => updateField("email", value)}
          required
        />
        <FormField
          label="Phone"
          name="phone"
          value={values.phone}
          onChange={(value) => updateField("phone", value)}
          required
        />
        <FormField
          label="Role Applied For"
          name="position"
          value={values.position}
          onChange={(value) => updateField("position", value)}
          required
        />
        <FormField
          label="Years of Experience"
          name="experience_years"
          type="number"
          min="0"
          value={values.experience_years}
          onChange={(value) => updateField("experience_years", value)}
          required
        />
        <FormField
          label="LinkedIn URL"
          name="linkedin_url"
          type="url"
          value={values.linkedin_url}
          onChange={(value) => updateField("linkedin_url", value)}
        />
        <FormField
          label="CV URL"
          name="cv_url"
          type="url"
          value={values.cv_url}
          onChange={(value) => updateField("cv_url", value)}
          className="sm:col-span-2"
        />
      </div>

      {validationError ? (
        <ErrorState message={validationError} />
      ) : null}

      {error ? <ErrorState message={error} /> : null}
      {success ? <SuccessMessage message={success} /> : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? submittingLabel : submitLabel}
      </button>
    </form>
  );
}

function FormField({
  label,
  name,
  value,
  onChange,
  type = "text",
  required = false,
  min,
  className = "",
}: {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
  min?: string;
  className?: string;
}) {
  return (
    <label className={`flex flex-col gap-1 text-sm ${className}`}>
      <span className="font-medium text-slate-700">
        {label}
        {required ? " *" : ""}
      </span>
      <input
        type={type}
        name={name}
        value={value}
        min={min}
        required={required}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
      />
    </label>
  );
}

function validateCandidateForm(values: CandidateFormValues): Record<string, string> {
  const errors: Record<string, string> = {};

  if (!values.full_name.trim()) {
    errors.full_name = "Full name is required.";
  }

  if (!values.email.trim()) {
    errors.email = "Email is required.";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
    errors.email = "Enter a valid email address.";
  }

  if (!values.phone.trim()) {
    errors.phone = "Phone is required.";
  }

  if (!values.position.trim()) {
    errors.position = "Role applied for is required.";
  }

  if (!values.experience_years.trim()) {
    errors.experience_years = "Years of experience is required.";
  } else if (Number(values.experience_years) < 0) {
    errors.experience_years = "Years of experience must be 0 or greater.";
  }

  return errors;
}

export function candidateToFormValues(
  candidate: {
    full_name: string;
    email: string;
    phone: string;
    position: string;
    experience_years: number;
    linkedin_url: string | null;
    cv_url: string | null;
  },
): CandidateFormValues {
  return {
    full_name: candidate.full_name,
    email: candidate.email,
    phone: candidate.phone,
    position: candidate.position,
    experience_years: String(candidate.experience_years),
    linkedin_url: candidate.linkedin_url ?? "",
    cv_url: candidate.cv_url ?? "",
  };
}
