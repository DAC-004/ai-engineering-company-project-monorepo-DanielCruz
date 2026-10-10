"use client";

import { FormEvent, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import { changePassword } from "@/lib/auth/session";

export const ChangePasswordForm = () => {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (newPassword !== confirmPassword) {
      setErrorMessage("New password and confirmation do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      await changePassword(currentPassword, newPassword);
      setSuccessMessage("Password updated successfully.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(
          "Unable to change the password. Check the API connection and try again.",
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="auth-form profile-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="change-current-password">Current password</label>
        <input
          id="change-current-password"
          name="current_password"
          type="password"
          autoComplete="current-password"
          required
          value={currentPassword}
          onChange={(event) => setCurrentPassword(event.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="change-new-password">New password</label>
        <input
          id="change-new-password"
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
        <label htmlFor="change-confirm-password">Confirm new password</label>
        <input
          id="change-confirm-password"
          name="confirm_password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
      </div>

      {successMessage ? (
        <p className="form-success" role="status">
          {successMessage}
        </p>
      ) : null}

      {errorMessage ? (
        <p className="form-error" role="alert">
          {errorMessage}
        </p>
      ) : null}

      <button type="submit" className="btn-primary" disabled={isSubmitting}>
        {isSubmitting ? "Updating…" : "Change password"}
      </button>
    </form>
  );
};
