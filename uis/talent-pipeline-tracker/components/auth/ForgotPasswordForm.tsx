"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import { requestPasswordReset } from "@/lib/auth/session";

const CONFIRMATION_MESSAGE =
  "If that address is registered, you'll receive a link shortly";

export const ForgotPasswordForm = () => {
  const [email, setEmail] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const formDisabled = isSubmitting || isSubmitted;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await requestPasswordReset(email.trim());
      // Confirmation is shown for every successful HTTP response so the UI
      // never reveals whether the address belongs to an account.
      setIsSubmitted(true);
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(
          "Unable to submit the reset request. Check the API connection and try again.",
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="forgot-email">Email</label>
        <input
          id="forgot-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          disabled={formDisabled}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>

      {isSubmitted ? (
        <p className="form-success" role="status">
          {CONFIRMATION_MESSAGE}
        </p>
      ) : null}

      {errorMessage ? (
        <p className="form-error" role="alert">
          {errorMessage}
        </p>
      ) : null}

      <button type="submit" className="btn-primary" disabled={formDisabled}>
        {isSubmitting
          ? "Sending…"
          : isSubmitted
            ? "Request sent"
            : "Send reset link"}
      </button>

      <p className="auth-switch">
        Remembered your password? <Link href="/login">Sign in</Link>
      </p>
    </form>
  );
};
