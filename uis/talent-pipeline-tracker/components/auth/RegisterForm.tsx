"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { ErrorRecovery } from "@/components/auth/ErrorRecovery";
import { ApiError, type FieldErrors } from "@/lib/auth/types";
import { GENERIC_ERROR_MESSAGE } from "@/lib/auth/userFacingError";
import { registerAndAuthenticate, storeSessionToken } from "@/lib/auth/session";

const emptyFields = {
  email: "",
  password: "",
  name: "",
  phone: "",
  address: "",
};

export const RegisterForm = () => {
  const router = useRouter();
  const [fields, setFields] = useState(emptyFields);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const updateField = (name: keyof typeof emptyFields, value: string) => {
    setFields((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});
    setIsSubmitting(true);

    try {
      const tokenResponse = await registerAndAuthenticate({
        email: fields.email.trim(),
        password: fields.password,
        name: fields.name,
        phone: fields.phone,
        address: fields.address,
      });
      storeSessionToken(tokenResponse.access_token);
      router.replace("/");
    } catch (error) {
      if (error instanceof ApiError) {
        if (Object.keys(error.fieldErrors).length > 0) {
          setFieldErrors(error.fieldErrors);
        }
        setFormError(error.message);
      } else {
        setFormError(GENERIC_ERROR_MESSAGE);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="register-email">Email</label>
        <input
          id="register-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={fields.email}
          onChange={(event) => updateField("email", event.target.value)}
          aria-invalid={Boolean(fieldErrors.email)}
        />
        {fieldErrors.email ? (
          <p className="field-error" role="alert">
            {fieldErrors.email}
          </p>
        ) : null}
      </div>

      <div className="field">
        <label htmlFor="register-password">Password</label>
        <input
          id="register-password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={fields.password}
          onChange={(event) => updateField("password", event.target.value)}
          aria-invalid={Boolean(fieldErrors.password)}
        />
        {fieldErrors.password ? (
          <p className="field-error" role="alert">
            {fieldErrors.password}
          </p>
        ) : (
          <p className="field-hint">At least 8 characters.</p>
        )}
      </div>

      <fieldset className="optional-profile">
        <legend>Optional profile</legend>
        <p className="field-hint">
          These fields seed the linked Profile created by POST /users.
        </p>

        <div className="field">
          <label htmlFor="register-name">Name</label>
          <input
            id="register-name"
            name="name"
            type="text"
            autoComplete="name"
            value={fields.name}
            onChange={(event) => updateField("name", event.target.value)}
            aria-invalid={Boolean(fieldErrors.name)}
          />
          {fieldErrors.name ? (
            <p className="field-error" role="alert">
              {fieldErrors.name}
            </p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="register-phone">Phone</label>
          <input
            id="register-phone"
            name="phone"
            type="tel"
            autoComplete="tel"
            value={fields.phone}
            onChange={(event) => updateField("phone", event.target.value)}
            aria-invalid={Boolean(fieldErrors.phone)}
          />
          {fieldErrors.phone ? (
            <p className="field-error" role="alert">
              {fieldErrors.phone}
            </p>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="register-address">Address</label>
          <input
            id="register-address"
            name="address"
            type="text"
            autoComplete="street-address"
            value={fields.address}
            onChange={(event) => updateField("address", event.target.value)}
            aria-invalid={Boolean(fieldErrors.address)}
          />
          {fieldErrors.address ? (
            <p className="field-error" role="alert">
              {fieldErrors.address}
            </p>
          ) : null}
        </div>
      </fieldset>

      {formError ? <ErrorRecovery message={formError} /> : null}

      <button type="submit" className="btn-primary" disabled={isSubmitting}>
        {isSubmitting ? "Creating account…" : "Create account"}
      </button>

      <p className="auth-switch">
        Already registered? <Link href="/login">Sign in</Link>
      </p>
    </form>
  );
};
