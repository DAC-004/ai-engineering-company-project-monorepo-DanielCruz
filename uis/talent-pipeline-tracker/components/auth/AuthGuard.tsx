"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { hasAccessToken } from "@/lib/auth/token";

type AuthGuardProps = {
  children: ReactNode;
};

/**
 * Client-side route protection for authenticated views.
 *
 * AUTH-02 requires checking localStorage for the JWT and redirecting to /login
 * when it is absent. Next.js middleware cannot read localStorage, so this guard
 * runs in the browser after mount.
 */
export const AuthGuard = ({ children }: AuthGuardProps) => {
  const router = useRouter();
  const [sessionState, setSessionState] = useState<
    "checking" | "authenticated" | "anonymous"
  >("checking");

  useEffect(() => {
    // Defer the localStorage read until after paint so the guard stays a
    // client-only sync with browser storage (not a cascading render during SSR).
    const frameId = window.requestAnimationFrame(() => {
      if (hasAccessToken()) {
        setSessionState("authenticated");
        return;
      }
      setSessionState("anonymous");
      router.replace("/login");
    });

    return () => window.cancelAnimationFrame(frameId);
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
