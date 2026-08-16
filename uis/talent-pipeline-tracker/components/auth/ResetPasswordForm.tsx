"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import { resetPasswordWithToken } from "@/lib/auth/session";

export const ResetPasswordForm = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = (searchParams.get("token") ?? "").trim();

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [tokenInvalid, setTokenInvalid] = useState(!token);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (!token) {
      setTokenInvalid(true);
      setErrorMessage("This reset link is missing a token.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMessage("New password and confirmation do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      await resetPasswordWithToken(token, newPassword);
      router.replace("/login?reset=success");
    } catch (error) {
      if (error instanceof ApiError) {
        setTokenInvalid(error.status === 400);
        setErrorMessage(error.message);
      } else {
        setErrorMessage(
          "Unable to reset the password. Check the API connection and try again.",
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      {!token ? (
        <p className="form-error" role="alert">
          This reset link is invalid or incomplete.
        </p>
      ) : null}

      <div className="field">
        <label htmlFor="reset-new-password">New password</label>
        <input
          id="reset-new-password"
          name="new_password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
        />
        <p className="field-hint">At least 8 characters.</p>
      </div>

      <div className="field">
        <label htmlFor="reset-confirm-password">Confirm new password</label>
        <input
          id="reset-confirm-password"
          name="confirm_password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
      </div>

      {errorMessage ? (
        <p className="form-error" role="alert">
          {errorMessage}
        </p>
      ) : null}

      {tokenInvalid ? (
        <p className="auth-switch">
          Need a new link? <Link href="/forgot-password">Forgot your password?</Link>
        </p>
      ) : null}

      <button type="submit" className="btn-primary" disabled={isSubmitting || !token}>
        {isSubmitting ? "Updating…" : "Update password"}
      </button>

      <p className="auth-switch">
        Back to <Link href="/login">Sign in</Link>
      </p>
    </form>
  );
};
