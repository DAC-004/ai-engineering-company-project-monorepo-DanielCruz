"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import { fetchCurrentUser, loginWithPassword, storeSessionToken } from "@/lib/auth/session";
import { track } from "@/src/services/telemetry";

export const LoginForm = () => {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      const tokenResponse = await loginWithPassword(email.trim(), password);
      storeSessionToken(tokenResponse.access_token);
      const currentUser = await fetchCurrentUser();
      track("user_login_succeeded", {
        auth_method: "password",
        role: currentUser.role,
      });
      router.replace("/");
    } catch (error) {
      if (error instanceof ApiError) {
        const failureReason =
          error.status === 422
            ? "malformed_request"
            : error.message.toLowerCase().includes("inactive")
              ? "inactive_user"
              : "invalid_credentials";
        track("user_login_failed", { failure_reason: failureReason });
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Unable to sign in. Check the API connection and try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>

      {errorMessage ? (
        <p className="form-error" role="alert">
          {errorMessage}
        </p>
      ) : null}

      <button type="submit" className="btn-primary" disabled={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in"}
      </button>

      <p className="auth-switch">
        Need an account? <Link href="/register">Register</Link>
      </p>
    </form>
  );
};
