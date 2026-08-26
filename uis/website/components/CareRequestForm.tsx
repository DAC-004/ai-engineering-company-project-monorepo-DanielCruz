"use client";

import { FormEvent, useMemo, useState } from "react";

const COUNTRY_LOCATIONS: Record<"US" | "UK", string[]> = {
  US: ["Austin TX", "Houston TX", "Miami FL", "Orlando FL", "Atlanta GA"],
  UK: ["London", "Manchester"],
};

const COUNTRY_PAYMENTS: Record<"US" | "UK", string[]> = {
  US: ["Private Insurance (US)", "Medicare (US)", "Medicaid (US)"],
  UK: ["Private Pay (UK)", "NHS Contract (UK)"],
};

const SERVICE_LINES = [
  "Primary Care",
  "Specialist Consultation",
  "Chronic Disease Management",
  "Preventive Health Programme",
] as const;

const COMMUNICATION_CHANNELS = ["SMS", "Email", "Phone Call"] as const;

const TIME_WINDOWS = [
  "Morning (08:00-12:00)",
  "Afternoon (12:00-17:00)",
  "Evening (17:00-20:00)",
] as const;

const PHONE_PATTERNS: Record<"US" | "UK", RegExp> = {
  US: /^\+1\d{10}$/,
  UK: /^\+44\d{10}$/,
};

const FIELD_NAMES = [
  "full_name",
  "date_of_birth",
  "email",
  "phone",
  "market_country",
  "clinic_location",
  "service_line",
  "preferred_date",
  "preferred_time_window",
  "communication_channel",
  "payment_model",
  "member_identifier",
  "consent_data_processing",
  "consent_contact",
] as const;

type FieldName = (typeof FIELD_NAMES)[number];
type MarketCountry = "" | "US" | "UK";
type FieldErrors = Partial<Record<FieldName, string>>;
type FieldVisualState = Partial<Record<FieldName, "error" | "success">>;

type FormValues = {
  full_name: string;
  date_of_birth: string;
  email: string;
  phone: string;
  market_country: MarketCountry;
  clinic_location: string;
  service_line: string;
  preferred_date: string;
  preferred_time_window: string;
  communication_channel: string;
  payment_model: string;
  member_identifier: string;
  consent_data_processing: boolean;
  consent_contact: boolean;
  patient_notes: string;
};

const EMPTY_VALUES: FormValues = {
  full_name: "",
  date_of_birth: "",
  email: "",
  phone: "",
  market_country: "",
  clinic_location: "",
  service_line: "",
  preferred_date: "",
  preferred_time_window: "",
  communication_channel: "",
  payment_model: "",
  member_identifier: "",
  consent_data_processing: false,
  consent_contact: false,
  patient_notes: "",
};

const inputClassName = (state: "error" | "success" | undefined, disabled = false): string => {
  const base =
    "w-full rounded-md border px-3.5 py-2.5 text-base focus:border-hcBlue focus:outline-none focus:ring-2 focus:ring-hcBlue/20";
  const disabledClass = disabled
    ? " cursor-not-allowed bg-slate-100 text-slate-500"
    : "";
  if (state === "error") {
    return `${base} border-red-600 ring-2 ring-red-600/20${disabledClass}`;
  }
  if (state === "success") {
    return `${base} border-emerald-600 ring-2 ring-emerald-600/20${disabledClass}`;
  }
  return `${base} border-slate-300${disabledClass}`;
};

const isAdult = (dateString: string): boolean => {
  const dob = new Date(`${dateString}T00:00:00`);
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const monthDiff = today.getMonth() - dob.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    age -= 1;
  }
  return age >= 18;
};

const isFutureDate = (dateString: string): boolean => {
  const selected = new Date(`${dateString}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return selected >= today;
};

const validateField = (fieldName: FieldName, data: FormValues): string => {
  switch (fieldName) {
    case "full_name":
      if (!data.full_name) {
        return "Please enter your full name.";
      }
      if (!/^[A-Za-z\s'.-]{2,80}$/.test(data.full_name)) {
        return "Enter your full name using letters and standard punctuation only.";
      }
      return "";
    case "date_of_birth":
      if (!data.date_of_birth) {
        return "Please enter your date of birth.";
      }
      if (!isAdult(data.date_of_birth)) {
        return "You must be at least 18 years old to submit this form.";
      }
      return "";
    case "email":
      if (!data.email) {
        return "Please enter your email address.";
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
        return "Enter a valid email address so we can contact you.";
      }
      return "";
    case "phone":
      if (!data.phone) {
        return "Please enter your phone number.";
      }
      if (!data.market_country) {
        return "Please choose your country of care before entering a phone number.";
      }
      if (!PHONE_PATTERNS[data.market_country].test(data.phone)) {
        return data.market_country === "US"
          ? "For United States care requests, enter a phone number using +1 followed by 10 digits."
          : "For United Kingdom care requests, enter a phone number using +44 followed by 10 digits.";
      }
      return "";
    case "market_country":
      return data.market_country ? "" : "Please choose the country where you want care.";
    case "clinic_location":
      if (!data.clinic_location) {
        return "Please choose your preferred clinic location.";
      }
      if (
        data.market_country &&
        !COUNTRY_LOCATIONS[data.market_country].includes(data.clinic_location)
      ) {
        return "Choose a clinic location that matches your selected country of care.";
      }
      return "";
    case "service_line":
      if (!data.service_line) {
        return "Please choose the service you need.";
      }
      if (!SERVICE_LINES.includes(data.service_line as (typeof SERVICE_LINES)[number])) {
        return "Choose Primary Care, Specialist Consultation, Chronic Disease Management, or Preventive Health Programme.";
      }
      return "";
    case "preferred_date":
      if (!data.preferred_date) {
        return "Please select your preferred appointment date.";
      }
      if (!isFutureDate(data.preferred_date)) {
        return "Choose today or a future date for your appointment request.";
      }
      return "";
    case "preferred_time_window":
      if (!data.preferred_time_window) {
        return "Please choose a preferred appointment window.";
      }
      if (!TIME_WINDOWS.includes(data.preferred_time_window as (typeof TIME_WINDOWS)[number])) {
        return "Choose Morning (08:00-12:00), Afternoon (12:00-17:00), or Evening (17:00-20:00).";
      }
      return "";
    case "communication_channel":
      if (!data.communication_channel) {
        return "Please choose how you would like to receive reminders.";
      }
      if (
        !COMMUNICATION_CHANNELS.includes(
          data.communication_channel as (typeof COMMUNICATION_CHANNELS)[number],
        )
      ) {
        return "Choose SMS, Email, or Phone Call.";
      }
      return "";
    case "payment_model":
      if (!data.payment_model) {
        return "Please choose your payment model.";
      }
      if (
        data.market_country &&
        !COUNTRY_PAYMENTS[data.market_country].includes(data.payment_model)
      ) {
        return "Choose a payment model that matches your selected country of care.";
      }
      return "";
    case "member_identifier":
      if (!data.member_identifier) {
        return "Please enter your insurance or NHS member identifier.";
      }
      if (!data.payment_model) {
        return "Please choose your payment model before entering a member identifier.";
      }
      if (data.payment_model === "NHS Contract (UK)" && !/^\d{10}$/.test(data.member_identifier)) {
        return "For NHS Contract (UK), enter a 10-digit member identifier.";
      }
      if (
        data.payment_model !== "NHS Contract (UK)" &&
        !/^[A-Za-z0-9-]{6,20}$/.test(data.member_identifier)
      ) {
        return "Enter an insurance member identifier with 6 to 20 letters, numbers, or hyphens.";
      }
      return "";
    case "consent_data_processing":
      return data.consent_data_processing
        ? ""
        : "Please confirm that you understand the data processing terms.";
    case "consent_contact":
      return data.consent_contact
        ? ""
        : "Please confirm that HealthCore may send appointment reminders.";
    default:
      return "";
  }
};

export const CareRequestForm = () => {
  const [values, setValues] = useState<FormValues>(EMPTY_VALUES);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [visualState, setVisualState] = useState<FieldVisualState>({});
  const [status, setStatus] = useState<{ kind: "error" | "success"; message: string } | null>(
    null,
  );

  const clinicOptions = useMemo(
    () => (values.market_country ? COUNTRY_LOCATIONS[values.market_country] : []),
    [values.market_country],
  );
  const paymentOptions = useMemo(
    () => (values.market_country ? COUNTRY_PAYMENTS[values.market_country] : []),
    [values.market_country],
  );

  const applyFieldResult = (
    fieldName: FieldName,
    nextValues: FormValues,
    showSuccess: boolean,
  ): boolean => {
    const message = validateField(fieldName, nextValues);
    setErrors((current) => {
      const next = { ...current };
      if (message) {
        next[fieldName] = message;
      } else {
        delete next[fieldName];
      }
      return next;
    });
    setVisualState((current) => {
      const next = { ...current };
      if (message) {
        next[fieldName] = "error";
      } else if (showSuccess) {
        next[fieldName] = "success";
      } else {
        delete next[fieldName];
      }
      return next;
    });
    return message === "";
  };

  const updateValue = <K extends keyof FormValues>(fieldName: K, value: FormValues[K]) => {
    setValues((current) => {
      const next = { ...current, [fieldName]: value };
      if (fieldName === "market_country") {
        next.clinic_location = "";
        next.payment_model = "";
      }
      return next;
    });
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const failed: FieldName[] = [];
    for (const fieldName of FIELD_NAMES) {
      if (!applyFieldResult(fieldName, values, true)) {
        failed.push(fieldName);
      }
    }
    if (failed.length > 0) {
      setStatus({
        kind: "error",
        message: "Please review the highlighted fields and try submitting your care request again.",
      });
      document.getElementById(failed[0])?.focus();
      return;
    }
    setValues(EMPTY_VALUES);
    setErrors({});
    setVisualState({});
    setStatus({
      kind: "success",
      message:
        "Your care request has been submitted. A HealthCore team member will review your details and contact you using the information provided.",
    });
  };

  const handleReset = () => {
    setValues(EMPTY_VALUES);
    setErrors({});
    setVisualState({});
    setStatus(null);
  };

  return (
    <section className="rounded-2xl bg-white p-7 shadow-sm ring-1 ring-slate-200 sm:p-9 lg:p-10">
      <div
        id="form-status"
        className={`mb-6 rounded-md border px-4 py-3 text-base ${
          status
            ? status.kind === "error"
              ? "border-red-300 bg-red-50 text-red-800"
              : "border-emerald-300 bg-emerald-50 text-emerald-800"
            : "hidden"
        }`}
        role="status"
        aria-live="polite"
      >
        {status?.message ?? ""}
      </div>

      <form id="healthcore-application-form" noValidate onSubmit={handleSubmit} onReset={handleReset}>
        <fieldset className="grid gap-6 md:grid-cols-2">
          <legend className="mb-5 text-xl font-semibold text-hcBlue lg:text-2xl">
            Patient Information
          </legend>

          <div>
            <label htmlFor="full_name" className="mb-2 block text-base font-medium">
              Full Name *
            </label>
            <input
              id="full_name"
              name="full_name"
              type="text"
              autoComplete="name"
              required
              value={values.full_name}
              onChange={(event) => updateValue("full_name", event.target.value)}
              onBlur={() => applyFieldResult("full_name", values, true)}
              aria-invalid={errors.full_name ? true : undefined}
              aria-describedby={errors.full_name ? "full_name_error" : undefined}
              className={inputClassName(visualState.full_name)}
            />
            <p id="full_name_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.full_name ?? ""}
            </p>
          </div>

          <div>
            <label htmlFor="date_of_birth" className="mb-2 block text-base font-medium">
              Date of Birth *
            </label>
            <input
              id="date_of_birth"
              name="date_of_birth"
              type="date"
              required
              value={values.date_of_birth}
              onChange={(event) => updateValue("date_of_birth", event.target.value)}
              onBlur={() => applyFieldResult("date_of_birth", values, true)}
              aria-invalid={errors.date_of_birth ? true : undefined}
              aria-describedby={errors.date_of_birth ? "date_of_birth_error" : undefined}
              className={inputClassName(visualState.date_of_birth)}
            />
            <p id="date_of_birth_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.date_of_birth ?? ""}
            </p>
          </div>

          <div>
            <label htmlFor="email" className="mb-2 block text-base font-medium">
              Email Address *
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={values.email}
              onChange={(event) => updateValue("email", event.target.value)}
              onBlur={() => applyFieldResult("email", values, true)}
              aria-invalid={errors.email ? true : undefined}
              aria-describedby={errors.email ? "email_error" : undefined}
              className={inputClassName(visualState.email)}
            />
            <p id="email_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.email ?? ""}
            </p>
          </div>

          <div>
            <label htmlFor="phone" className="mb-2 block text-base font-medium">
              Phone Number *
            </label>
            <input
              id="phone"
              name="phone"
              type="tel"
              autoComplete="tel"
              required
              placeholder="United States: +1XXXXXXXXXX | United Kingdom: +44XXXXXXXXXX"
              value={values.phone}
              onChange={(event) => updateValue("phone", event.target.value)}
              onBlur={() => applyFieldResult("phone", values, true)}
              aria-invalid={errors.phone ? true : undefined}
              aria-describedby={errors.phone ? "phone_error" : undefined}
              className={inputClassName(visualState.phone)}
            />
            <p id="phone_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.phone ?? ""}
            </p>
          </div>
        </fieldset>

        <fieldset className="mt-10 grid gap-6 md:grid-cols-2">
          <legend className="mb-5 text-xl font-semibold text-hcBlue lg:text-2xl">
            Clinic and Appointment Preferences
          </legend>

          <div>
            <label htmlFor="market_country" className="mb-2 block text-base font-medium">
              Country of Care *
            </label>
            <select
              id="market_country"
              name="market_country"
              required
              value={values.market_country}
              onChange={(event) => {
                const country = event.target.value as MarketCountry;
                const nextValues: FormValues = {
                  ...values,
                  market_country: country,
                  clinic_location: "",
                  payment_model: "",
                };
                setValues(nextValues);
                applyFieldResult("market_country", nextValues, true);
                applyFieldResult("phone", nextValues, false);
                applyFieldResult("clinic_location", nextValues, false);
                applyFieldResult("payment_model", nextValues, false);
                applyFieldResult("member_identifier", nextValues, false);
              }}
              aria-invalid={errors.market_country ? true : undefined}
              aria-describedby={errors.market_country ? "market_country_error" : undefined}
              className={inputClassName(visualState.market_country)}
            >
              <option value="">Choose a country</option>
              <option value="US">United States</option>
              <option value="UK">United Kingdom</option>
            </select>
            <p id="market_country_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.market_country ?? ""}
            </p>
          </div>

          <div>
            <label htmlFor="clinic_location" className="mb-2 block text-base font-medium">
              Preferred Clinic Location *
            </label>
            <select
              id="clinic_location"
              name="clinic_location"
              required
              disabled={!values.market_country}
              value={values.clinic_location}
              onChange={(event) => updateValue("clinic_location", event.target.value)}
              onBlur={() => applyFieldResult("clinic_location", values, true)}
              aria-invalid={errors.clinic_location ? true : undefined}
              aria-describedby={errors.clinic_location ? "clinic_location_error" : undefined}
              className={inputClassName(visualState.clinic_location, !values.market_country)}
            >
              <option value="">
                {values.market_country ? "Choose a clinic location" : "Choose a country of care first"}
              </option>
              {clinicOptions.map((location) => (
                <option key={location} value={location}>
                  {location}
                </option>
              ))}
            </select>
            <p id="clinic_location_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.clinic_location ?? ""}
            </p>
          </div>

          <div>
            <label htmlFor="service_line" className="mb-2 block text-base font-medium">
              Service Needed *
            </label>
            <select
              id="service_line"
              name="service_line"
              required
              value={values.service_line}
              onChange={(event) => updateValue("service_line", event.target.value)}
              onBlur={() => applyFieldResult("service_line", values, true)}
              aria-invalid={errors.service_line ? true : undefined}
              aria-describedby={errors.service_line ? "service_line_error" : undefined}
              className={inputClassName(visualState.service_line)}
            >
              <option value="">Choose a service</option>
              {SERVICE_LINES.map((service) => (
                <option key={service} value={service}>
                  {service}
                </option>
              ))}
            </select>
            <p id="service_line_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.service_line ?? ""}
            </p>
          </div>

          <div>
            <label htmlFor="preferred_date" className="mb-2 block text-base font-medium">
              Preferred Appointment Date *
            </label>
            <input
              id="preferred_date"
              name="preferred_date"
              type="date"
              required
              value={values.preferred_date}
              onChange={(event) => updateValue("preferred_date", event.target.value)}
              onBlur={() => applyFieldResult("preferred_date", values, true)}
              aria-invalid={errors.preferred_date ? true : undefined}
              aria-describedby={errors.preferred_date ? "preferred_date_error" : undefined}
              className={inputClassName(visualState.preferred_date)}
            />
            <p id="preferred_date_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.preferred_date ?? ""}
            </p>
          </div>

          <div>
            <label htmlFor="preferred_time_window" className="mb-2 block text-base font-medium">
              Preferred Appointment Window *
            </label>
            <select
              id="preferred_time_window"
              name="preferred_time_window"
              required
              value={values.preferred_time_window}
              onChange={(event) => updateValue("preferred_time_window", event.target.value)}
              onBlur={() => applyFieldResult("preferred_time_window", values, true)}
              aria-invalid={errors.preferred_time_window ? true : undefined}
              aria-describedby={errors.preferred_time_window ? "preferred_time_window_error" : undefined}
              className={inputClassName(visualState.preferred_time_window)}
            >
              <option value="">Choose a time window</option>
              {TIME_WINDOWS.map((window) => (
                <option key={window} value={window}>
                  {window}
                </option>
              ))}
            </select>
            <p id="preferred_time_window_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.preferred_time_window ?? ""}
            </p>
          </div>

          <div>
            <label htmlFor="communication_channel" className="mb-2 block text-base font-medium">
              Preferred Reminder Method *
            </label>
            <select
              id="communication_channel"
              name="communication_channel"
              required
              value={values.communication_channel}
              onChange={(event) => updateValue("communication_channel", event.target.value)}
              onBlur={() => applyFieldResult("communication_channel", values, true)}
              aria-invalid={errors.communication_channel ? true : undefined}
              aria-describedby={errors.communication_channel ? "communication_channel_error" : undefined}
              className={inputClassName(visualState.communication_channel)}
            >
              <option value="">Choose a reminder method</option>
              {COMMUNICATION_CHANNELS.map((channel) => (
                <option key={channel} value={channel}>
                  {channel}
                </option>
              ))}
            </select>
            <p id="communication_channel_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.communication_channel ?? ""}
            </p>
          </div>
        </fieldset>

        <fieldset className="mt-10 grid gap-6 md:grid-cols-2">
          <legend className="mb-5 text-xl font-semibold text-hcBlue lg:text-2xl">
            Payment Details and Consent
          </legend>

          <div>
            <label htmlFor="payment_model" className="mb-2 block text-base font-medium">
              Payment Model *
            </label>
            <select
              id="payment_model"
              name="payment_model"
              required
              disabled={!values.market_country}
              value={values.payment_model}
              onChange={(event) => {
                const nextValues = { ...values, payment_model: event.target.value };
                setValues(nextValues);
                applyFieldResult("payment_model", nextValues, true);
                applyFieldResult("member_identifier", nextValues, false);
              }}
              aria-invalid={errors.payment_model ? true : undefined}
              aria-describedby={errors.payment_model ? "payment_model_error" : undefined}
              className={inputClassName(visualState.payment_model, !values.market_country)}
            >
              <option value="">
                {values.market_country ? "Choose a payment model" : "Choose a country of care first"}
              </option>
              {paymentOptions.map((payment) => (
                <option key={payment} value={payment}>
                  {payment}
                </option>
              ))}
            </select>
            <p id="payment_model_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.payment_model ?? ""}
            </p>
          </div>

          <div>
            <label htmlFor="member_identifier" className="mb-2 block text-base font-medium">
              Insurance or NHS Member Identifier *
            </label>
            <input
              id="member_identifier"
              name="member_identifier"
              type="text"
              required
              value={values.member_identifier}
              onChange={(event) => updateValue("member_identifier", event.target.value)}
              onBlur={() => applyFieldResult("member_identifier", values, true)}
              aria-invalid={errors.member_identifier ? true : undefined}
              aria-describedby={errors.member_identifier ? "member_identifier_error" : undefined}
              className={inputClassName(visualState.member_identifier)}
            />
            <p id="member_identifier_error" className="mt-1 text-sm text-red-700" aria-live="polite">
              {errors.member_identifier ?? ""}
            </p>
          </div>

          <div className="md:col-span-2">
            <label htmlFor="patient_notes" className="mb-2 block text-base font-medium">
              Additional Notes (optional)
            </label>
            <textarea
              id="patient_notes"
              name="patient_notes"
              rows={4}
              value={values.patient_notes}
              onChange={(event) => updateValue("patient_notes", event.target.value)}
              className="w-full rounded-md border border-slate-300 px-3.5 py-2.5 text-base focus:border-hcBlue focus:outline-none focus:ring-2 focus:ring-hcBlue/20"
            />
            <p className="mt-2 text-sm text-slate-600 lg:text-base">
              Share only the information needed to help HealthCore understand your request for care.
            </p>
          </div>

          <div className="md:col-span-2">
            <div className="rounded-md border border-slate-300 p-5 lg:p-6">
              <div className="flex items-start gap-3">
                <input
                  id="consent_data_processing"
                  name="consent_data_processing"
                  type="checkbox"
                  required
                  checked={values.consent_data_processing}
                  onChange={(event) =>
                    updateValue("consent_data_processing", event.target.checked)
                  }
                  onBlur={() => applyFieldResult("consent_data_processing", values, true)}
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-hcBlue focus:ring-hcBlue"
                />
                <label htmlFor="consent_data_processing" className="text-base leading-relaxed lg:text-lg">
                  I understand that HealthCore will process my personal health information in line with
                  HIPAA in the US and UK GDPR in the UK. *
                </label>
              </div>
              <p
                id="consent_data_processing_error"
                className="mt-1 text-sm text-red-700"
                aria-live="polite"
              >
                {errors.consent_data_processing ?? ""}
              </p>

              <div className="mt-5 flex items-start gap-3">
                <input
                  id="consent_contact"
                  name="consent_contact"
                  type="checkbox"
                  required
                  checked={values.consent_contact}
                  onChange={(event) => updateValue("consent_contact", event.target.checked)}
                  onBlur={() => applyFieldResult("consent_contact", values, true)}
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-hcBlue focus:ring-hcBlue"
                />
                <label htmlFor="consent_contact" className="text-base leading-relaxed lg:text-lg">
                  I agree to receive appointment reminders using the contact method I selected above. *
                </label>
              </div>
              <p id="consent_contact_error" className="mt-1 text-sm text-red-700" aria-live="polite">
                {errors.consent_contact ?? ""}
              </p>
            </div>
          </div>
        </fieldset>

        <div className="mt-10 flex flex-wrap gap-4">
          <button
            type="submit"
            className="rounded-lg bg-hcBlue px-6 py-3.5 text-base font-semibold text-white shadow-sm hover:bg-hcTeal focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-hcBlue lg:px-8 lg:py-4 lg:text-lg"
          >
            Submit Care Request
          </button>
          <button
            type="reset"
            className="rounded-lg border border-slate-300 bg-white px-6 py-3.5 text-base font-semibold text-slate-700 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-hcBlue lg:px-8 lg:py-4 lg:text-lg"
          >
            Clear Entered Details
          </button>
        </div>
      </form>
    </section>
  );
};
