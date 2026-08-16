"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ErrorRecovery } from "@/components/auth/ErrorRecovery";
import { ApiError } from "@/lib/auth/types";
import { GENERIC_ERROR_MESSAGE } from "@/lib/auth/userFacingError";
import { fetchCurrentUser } from "@/lib/auth/session";
import { hasAccessToken } from "@/lib/auth/token";

type AuthGuardProps = {
  children: ReactNode;
};

type SessionState = "checking" | "authenticated" | "anonymous" | "error";

/**
 * Client-side route protection for authenticated views.
 *
 * AUTH-02 requires redirecting to /login when the JWT is absent or invalid.
 * Presence alone is not sufficient: this guard validates the stored token
 * against GET /auth/me (AUTH-01). Next.js middleware cannot read localStorage,
 * so validation runs in the browser after mount.
 */
export const AuthGuard = ({ children }: AuthGuardProps) => {
  const router = useRouter();
  const [sessionState, setSessionState] = useState<SessionState>("checking");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const verifySession = async () => {
      setSessionState("checking");
      setErrorMessage(null);

      if (!hasAccessToken()) {
        if (!cancelled) {
          setSessionState("anonymous");
          router.replace("/login");
        }
        return;
      }

      try {
        // Server-side JWT validation via AUTH-01. A 401 from apiFetch clears
        // localStorage and redirects to /login before this catch runs.
        await fetchCurrentUser();
        if (!cancelled) {
          setSessionState("authenticated");
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        // 401 already cleared the session and redirected in apiFetch.
        if (error instanceof ApiError && error.status === 401) {
          setSessionState("anonymous");
          return;
        }

        setSessionState("error");
        setErrorMessage(
          error instanceof ApiError ? error.message : GENERIC_ERROR_MESSAGE,
        );
      }
    };

    void verifySession();

    return () => {
      cancelled = true;
    };
  }, [router, retryKey]);

  if (sessionState === "error") {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <ErrorRecovery
            message={
              errorMessage ??
              "The session could not be verified. Try again or sign in."
            }
            onRetry={() => setRetryKey((current) => current + 1)}
            retryLabel="Retry session check"
            signInHref="/login"
          />
        </div>
      </div>
    );
  }

  if (sessionState !== "authenticated") {
    return (
      <div className="auth-loading" role="status" aria-live="polite">
        Checking session…
      </div>
    );
  }

  return <>{children}</>;
};
