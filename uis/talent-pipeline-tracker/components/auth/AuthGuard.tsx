"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ApiError } from "@/lib/auth/types";
import { fetchCurrentUser } from "@/lib/auth/session";
import { hasAccessToken } from "@/lib/auth/token";

type AuthGuardProps = {
  children: ReactNode;
};

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
  const [sessionState, setSessionState] = useState<
    "checking" | "authenticated" | "anonymous"
  >("checking");

  useEffect(() => {
    let cancelled = false;

    const verifySession = async () => {
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

        setSessionState("anonymous");

        // 401 already cleared the session and redirected in apiFetch.
        // Any other failure must still deny protected-view access.
        if (!(error instanceof ApiError && error.status === 401)) {
          router.replace("/login");
        }
      }
    };

    void verifySession();

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (sessionState !== "authenticated") {
    return (
      <div className="auth-loading" role="status" aria-live="polite">
        Checking session…
      </div>
    );
  }

  return <>{children}</>;
};
