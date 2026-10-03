"use client";

import { useMemo, useState } from "react";

type MarketCountry = "US" | "UK" | "";

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
  patient_notes: string;
  consent_data_processing: boolean;
  consent_contact: boolean;
};

type ErrorMap = Partial<Record<keyof FormValues, string>>;

const countryLocations: Record<Exclude<MarketCountry, "">, string[]> = {
  US: ["Austin TX", "Houston TX", "Miami FL", "Orlando FL", "Atlanta GA"],
  UK: ["London", "Manchester"]
};

const countryPayments: Record<Exclude<MarketCountry, "">, string[]> = {
  US: ["Private Insurance (US)", "Medicare (US)", "Medicaid (US)"],
  UK: ["Private Pay (UK)", "NHS Contract (UK)"]
};

const serviceLines = [
  "Primary Care",
  "Specialist Consultation",
  "Chronic Disease Management",
  "Preventive Health Programme"
];

const communicationChannels = ["SMS", "Email", "Phone Call"];
const timeWindows = ["Morning (08:00-12:00)", "Afternoon (12:00-17:00)", "Evening (17:00-20:00)"];

const initialValues: FormValues = {
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
  patient_notes: "",
  consent_data_processing: false,
  consent_contact: false
};

function isAdult(dateString: string): boolean {
  const dob = new Date(`${dateString}T00:00:00`);
  if (Number.isNaN(dob.getTime())) return false;

  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const monthDiff = today.getMonth() - dob.getMonth();

  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    age -= 1;
  }

  return age >= 18;
}

function isTodayOrFutureDate(dateString: string): boolean {
  const selected = new Date(`${dateString}T00:00:00`);
  if (Number.isNaN(selected.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return selected >= today;
}

export function CareRequestForm() {
  const [values, setValues] = useState<FormValues>(initialValues);
  const [errors, setErrors] = useState<ErrorMap>({});
  const [successFields, setSuccessFields] = useState<Partial<Record<keyof FormValues, boolean>>>({});
  const [status, setStatus] = useState<{ kind: "success" | "error"; message: string } | null>(null);

  const clinicOptions = useMemo(() => {
    if (!values.market_country) return [];
    return countryLocations[values.market_country];
  }, [values.market_country]);

  const paymentOptions = useMemo(() => {
    if (!values.market_country) return [];
    return countryPayments[values.market_country];
  }, [values.market_country]);

  function validateField(fieldName: keyof FormValues, data: FormValues): string | null {
    switch (fieldName) {
      case "full_name":
        if (!data.full_name) return "Please enter your full name.";
        if (!/^[A-Za-z\s'.-]{2,80}$/.test(data.full_name)) {
          return "Enter your full name using letters and standard punctuation only.";
        }
        return null;
      case "date_of_birth":
        if (!data.date_of_birth) return "Please enter your date of birth.";
        if (!isAdult(data.date_of_birth)) return "You must be at least 18 years old to submit this form.";
        return null;
      case "email":
        if (!data.email) return "Please enter your email address.";
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) return "Enter a valid email address so we can contact you.";
        return null;
      case "phone":
        if (!data.phone) return "Please enter your phone number.";
        if (!data.market_country) return "Please choose your country of care before entering a phone number.";
        if (data.market_country === "US" && !/^\+1\d{10}$/.test(data.phone)) {
          return "For United States care requests, enter a phone number using +1 followed by 10 digits.";
        }
        if (data.market_country === "UK" && !/^\+44\d{10}$/.test(data.phone)) {
          return "For United Kingdom care requests, enter a phone number using +44 followed by 10 digits.";
        }
        return null;
      case "market_country":
        return data.market_country ? null : "Please choose the country where you want care.";
      case "clinic_location":
        if (!data.clinic_location) return "Please choose your preferred clinic location.";
        if (data.market_country && !countryLocations[data.market_country].includes(data.clinic_location)) {
          return "Choose a clinic location that matches your selected country of care.";
        }
        return null;
      case "service_line":
        if (!data.service_line) return "Please choose the service you need.";
        if (!serviceLines.includes(data.service_line)) {
          return "Choose Primary Care, Specialist Consultation, Chronic Disease Management, or Preventive Health Programme.";
        }
        return null;
      case "preferred_date":
        if (!data.preferred_date) return "Please select your preferred appointment date.";
        if (!isTodayOrFutureDate(data.preferred_date)) return "Choose today or a future date for your appointment request.";
        return null;
      case "preferred_time_window":
        if (!data.preferred_time_window) return "Please choose a preferred appointment window.";
        if (!timeWindows.includes(data.preferred_time_window)) {
          return "Choose Morning (08:00-12:00), Afternoon (12:00-17:00), or Evening (17:00-20:00).";
        }
        return null;
      case "communication_channel":
        if (!data.communication_channel) return "Please choose how you would like to receive reminders.";
        if (!communicationChannels.includes(data.communication_channel)) return "Choose SMS, Email, or Phone Call.";
        return null;
      case "payment_model":
        if (!data.payment_model) return "Please choose your payment model.";
        if (data.market_country && !countryPayments[data.market_country].includes(data.payment_model)) {
          return "Choose a payment model that matches your selected country of care.";
        }
        return null;
      case "member_identifier":
        if (!data.member_identifier) return "Please enter your insurance or NHS member identifier.";
        if (!data.payment_model) return "Please choose your payment model before entering a member identifier.";
        if (data.payment_model === "NHS Contract (UK)" && !/^\d{10}$/.test(data.member_identifier)) {
          return "For NHS Contract (UK), enter a 10-digit member identifier.";
        }
        if (data.payment_model !== "NHS Contract (UK)" && !/^[A-Za-z0-9-]{6,20}$/.test(data.member_identifier)) {
          return "Enter an insurance member identifier with 6 to 20 letters, numbers, or hyphens.";
        }
        return null;
      case "consent_data_processing":
        return data.consent_data_processing ? null : "Please confirm that you understand the data processing terms.";
      case "consent_contact":
        return data.consent_contact ? null : "Please confirm that HealthCore may send appointment reminders.";
      default:
        return null;
    }
  }

  function validateAll(data: FormValues) {
    const fieldNames = Object.keys(initialValues) as Array<keyof FormValues>;
    const nextErrors: ErrorMap = {};

    for (const fieldName of fieldNames) {
      if (fieldName === "patient_notes") {
        continue;
      }
      const error = validateField(fieldName, data);
      if (error) {
        nextErrors[fieldName] = error;
      }
    }

    return nextErrors;
  }

  function updateValue<K extends keyof FormValues>(field: K, value: FormValues[K]) {
    const nextValues = { ...values, [field]: value };

    if (field === "market_country") {
      nextValues.clinic_location = "";
      nextValues.payment_model = "";
      nextValues.member_identifier = "";
    }

    setValues(nextValues);
    setStatus(null);

    const currentError = validateField(field, nextValues);
    setErrors((prev) => ({ ...prev, [field]: currentError ?? undefined }));

    if (!currentError && field !== "patient_notes") {
      setSuccessFields((prev) => ({ ...prev, [field]: true }));
    }
  }

  function handleBlur(field: keyof FormValues) {
    if (field === "patient_notes") return;
    const error = validateField(field, values);
    setErrors((prev) => ({ ...prev, [field]: error ?? undefined }));
    setSuccessFields((prev) => ({ ...prev, [field]: !error }));
  }

  function fieldClass(field: keyof FormValues): string {
    const base = "w-full rounded-md border px-3.5 py-2.5 text-base focus:outline-none";
    if (errors[field]) {
      return `${base} border-red-600 ring-2 ring-red-600/20 focus:border-red-600`;
    }
    if (successFields[field]) {
      return `${base} border-emerald-600 ring-2 ring-emerald-600/20 focus:border-emerald-600`;
    }
    return `${base} border-slate-300 focus:border-[#0E3A5D] focus:ring-2 focus:ring-[#0E3A5D]/20`;
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validateAll(values);
    setErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) {
      setStatus({
        kind: "error",
        message: "Please review the highlighted fields and try submitting your care request again."
      });
      return;
    }

    setValues(initialValues);
    setErrors({});
    setSuccessFields({});
    setStatus({
      kind: "success",
      message:
        "Your care request has been submitted. A HealthCore team member will review your details and contact you using the information provided."
    });
  }

  return (
    <>
      {status ? (
        <div
          className={`mb-6 rounded-md border px-4 py-3 text-base ${
            status.kind === "error"
              ? "border-red-300 bg-red-50 text-red-800"
              : "border-emerald-300 bg-emerald-50 text-emerald-800"
          }`}
          role="status"
          aria-live="polite"
        >
          {status.message}
        </div>
      ) : null}

      <form id="healthcore-application-form" noValidate onSubmit={handleSubmit}>
        <fieldset className="grid gap-6 md:grid-cols-2">
          <legend className="mb-5 text-xl font-semibold text-[#0E3A5D] lg:text-2xl">Patient Information</legend>

          <div>
            <label htmlFor="full_name" className="mb-2 block text-base font-medium">Full Name *</label>
            <input id="full_name" name="full_name" type="text" required value={values.full_name} onBlur={() => handleBlur("full_name")} onChange={(e) => updateValue("full_name", e.target.value)} className={fieldClass("full_name")} />
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.full_name}</p>
          </div>

          <div>
            <label htmlFor="date_of_birth" className="mb-2 block text-base font-medium">Date of Birth *</label>
            <input id="date_of_birth" name="date_of_birth" type="date" required value={values.date_of_birth} onBlur={() => handleBlur("date_of_birth")} onChange={(e) => updateValue("date_of_birth", e.target.value)} className={fieldClass("date_of_birth")} />
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.date_of_birth}</p>
          </div>

          <div>
            <label htmlFor="email" className="mb-2 block text-base font-medium">Email Address *</label>
            <input id="email" name="email" type="email" required value={values.email} onBlur={() => handleBlur("email")} onChange={(e) => updateValue("email", e.target.value)} className={fieldClass("email")} />
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.email}</p>
          </div>

          <div>
            <label htmlFor="phone" className="mb-2 block text-base font-medium">Phone Number *</label>
            <input id="phone" name="phone" type="tel" required placeholder="United States: +1XXXXXXXXXX | United Kingdom: +44XXXXXXXXXX" value={values.phone} onBlur={() => handleBlur("phone")} onChange={(e) => updateValue("phone", e.target.value)} className={fieldClass("phone")} />
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.phone}</p>
          </div>
        </fieldset>

        <fieldset className="mt-10 grid gap-6 md:grid-cols-2">
          <legend className="mb-5 text-xl font-semibold text-[#0E3A5D] lg:text-2xl">Clinic and Appointment Preferences</legend>

          <div>
            <label htmlFor="market_country" className="mb-2 block text-base font-medium">Country of Care *</label>
            <select id="market_country" name="market_country" required value={values.market_country} onBlur={() => handleBlur("market_country")} onChange={(e) => updateValue("market_country", e.target.value as MarketCountry)} className={fieldClass("market_country")}>
              <option value="">Choose a country</option>
              <option value="US">United States</option>
              <option value="UK">United Kingdom</option>
            </select>
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.market_country}</p>
          </div>

          <div>
            <label htmlFor="clinic_location" className="mb-2 block text-base font-medium">Preferred Clinic Location *</label>
            <select id="clinic_location" name="clinic_location" required disabled={!values.market_country} value={values.clinic_location} onBlur={() => handleBlur("clinic_location")} onChange={(e) => updateValue("clinic_location", e.target.value)} className={`${fieldClass("clinic_location")} disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500`}>
              <option value="">{values.market_country ? "Choose a clinic location" : "Choose a country of care first"}</option>
              {clinicOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.clinic_location}</p>
          </div>

          <div>
            <label htmlFor="service_line" className="mb-2 block text-base font-medium">Service Needed *</label>
            <select id="service_line" name="service_line" required value={values.service_line} onBlur={() => handleBlur("service_line")} onChange={(e) => updateValue("service_line", e.target.value)} className={fieldClass("service_line")}>
              <option value="">Choose a service</option>
              {serviceLines.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.service_line}</p>
          </div>

          <div>
            <label htmlFor="preferred_date" className="mb-2 block text-base font-medium">Preferred Appointment Date *</label>
            <input id="preferred_date" name="preferred_date" type="date" required value={values.preferred_date} onBlur={() => handleBlur("preferred_date")} onChange={(e) => updateValue("preferred_date", e.target.value)} className={fieldClass("preferred_date")} />
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.preferred_date}</p>
          </div>

          <div>
            <label htmlFor="preferred_time_window" className="mb-2 block text-base font-medium">Preferred Appointment Window *</label>
            <select id="preferred_time_window" name="preferred_time_window" required value={values.preferred_time_window} onBlur={() => handleBlur("preferred_time_window")} onChange={(e) => updateValue("preferred_time_window", e.target.value)} className={fieldClass("preferred_time_window")}>
              <option value="">Choose a time window</option>
              {timeWindows.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.preferred_time_window}</p>
          </div>

          <div>
            <label htmlFor="communication_channel" className="mb-2 block text-base font-medium">Preferred Reminder Method *</label>
            <select id="communication_channel" name="communication_channel" required value={values.communication_channel} onBlur={() => handleBlur("communication_channel")} onChange={(e) => updateValue("communication_channel", e.target.value)} className={fieldClass("communication_channel")}>
              <option value="">Choose a reminder method</option>
              {communicationChannels.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.communication_channel}</p>
          </div>
        </fieldset>

        <fieldset className="mt-10 grid gap-6 md:grid-cols-2">
          <legend className="mb-5 text-xl font-semibold text-[#0E3A5D] lg:text-2xl">Payment Details and Consent</legend>

          <div>
            <label htmlFor="payment_model" className="mb-2 block text-base font-medium">Payment Model *</label>
            <select id="payment_model" name="payment_model" required disabled={!values.market_country} value={values.payment_model} onBlur={() => handleBlur("payment_model")} onChange={(e) => updateValue("payment_model", e.target.value)} className={`${fieldClass("payment_model")} disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500`}>
              <option value="">{values.market_country ? "Choose a payment model" : "Choose a country of care first"}</option>
              {paymentOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.payment_model}</p>
          </div>

          <div>
            <label htmlFor="member_identifier" className="mb-2 block text-base font-medium">Insurance or NHS Member Identifier *</label>
            <input id="member_identifier" name="member_identifier" type="text" required value={values.member_identifier} onBlur={() => handleBlur("member_identifier")} onChange={(e) => updateValue("member_identifier", e.target.value)} className={fieldClass("member_identifier")} />
            <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.member_identifier}</p>
          </div>

          <div className="md:col-span-2">
            <label htmlFor="patient_notes" className="mb-2 block text-base font-medium">Additional Notes (optional)</label>
            <textarea id="patient_notes" name="patient_notes" rows={4} value={values.patient_notes} onChange={(e) => updateValue("patient_notes", e.target.value)} className={fieldClass("patient_notes")} />
            <p className="mt-2 text-sm text-slate-600 lg:text-base">
              Share only the information needed to help HealthCore understand your request for care.
            </p>
          </div>

          <div className="md:col-span-2">
            <div className="rounded-md border border-slate-300 p-5 lg:p-6">
              <div className="flex items-start gap-3">
                <input id="consent_data_processing" name="consent_data_processing" type="checkbox" required checked={values.consent_data_processing} onBlur={() => handleBlur("consent_data_processing")} onChange={(e) => updateValue("consent_data_processing", e.target.checked)} className="mt-1 h-4 w-4 rounded border-slate-300 text-[#0E3A5D] focus:ring-[#0E3A5D]" />
                <label htmlFor="consent_data_processing" className="text-base leading-relaxed lg:text-lg">
                  I understand that HealthCore will process my personal health information in line
                  with HIPAA in the US and UK GDPR in the UK. *
                </label>
              </div>
              <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.consent_data_processing}</p>

              <div className="mt-5 flex items-start gap-3">
                <input id="consent_contact" name="consent_contact" type="checkbox" required checked={values.consent_contact} onBlur={() => handleBlur("consent_contact")} onChange={(e) => updateValue("consent_contact", e.target.checked)} className="mt-1 h-4 w-4 rounded border-slate-300 text-[#0E3A5D] focus:ring-[#0E3A5D]" />
                <label htmlFor="consent_contact" className="text-base leading-relaxed lg:text-lg">
                  I agree to receive appointment reminders using the contact method I selected above. *
                </label>
              </div>
              <p className="mt-1 text-sm text-red-700" aria-live="polite">{errors.consent_contact}</p>
            </div>
          </div>
        </fieldset>

        <div className="mt-10 flex flex-wrap gap-4">
          <button type="submit" className="rounded-lg bg-[#0E3A5D] px-6 py-3.5 text-base font-semibold text-white shadow-sm hover:bg-[#0E7490] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0E3A5D] lg:px-8 lg:py-4 lg:text-lg">
            Submit Care Request
          </button>
          <button
            type="button"
            onClick={() => {
              setValues(initialValues);
              setErrors({});
              setSuccessFields({});
              setStatus(null);
            }}
            className="rounded-lg border border-slate-300 bg-white px-6 py-3.5 text-base font-semibold text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0E3A5D] lg:px-8 lg:py-4 lg:text-lg"
          >
            Clear Entered Details
          </button>
        </div>
      </form>
    </>
  );
}
