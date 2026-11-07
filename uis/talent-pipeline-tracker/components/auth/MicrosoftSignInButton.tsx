"use client";

import { useState } from "react";

import { ErrorRecovery } from "@/components/auth/ErrorRecovery";
import { startMicrosoftFederated } from "@/lib/auth/federated";
import { ApiError } from "@/lib/auth/types";
import { GENERIC_ERROR_MESSAGE } from "@/lib/auth/userFacingError";

export const MicrosoftSignInButton = () => {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  const handleClick = async () => {
    setErrorMessage(null);
    setIsStarting(true);
    try {
      const started = await startMicrosoftFederated("login", { auth: false });
      window.location.assign(started.authorization_url);
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError ? error.message : GENERIC_ERROR_MESSAGE,
      );
      setIsStarting(false);
    }
  };

  return (
    <div className="federated-login">
      <p className="federated-login__rule">
        Microsoft sign-in works only for staff accounts IT already provisioned and
        linked from the profile. It does not create a HealthCore user.
      </p>
      {errorMessage ? <ErrorRecovery message={errorMessage} /> : null}
      <button
        type="button"
        className="btn-secondary"
        onClick={() => {
          void handleClick();
        }}
        disabled={isStarting}
      >
        {isStarting ? "Redirecting…" : "Sign in with Microsoft"}
      </button>
    </div>
  );
};
