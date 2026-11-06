"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ErrorRecovery } from "@/components/auth/ErrorRecovery";
import {
  completeMicrosoftFederated,
  isTokenResponse,
} from "@/lib/auth/federated";
import { fetchCurrentUser, storeSessionToken } from "@/lib/auth/session";
import { getAccessToken } from "@/lib/auth/token";
import { ApiError } from "@/lib/auth/types";
import { GENERIC_ERROR_MESSAGE } from "@/lib/auth/userFacingError";
import { track } from "@/src/services/telemetry";

const MicrosoftCallbackHandler = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const missingCallbackParams = !code || !state;
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!code || !state) {
      return;
    }

    const run = async () => {
      const existingToken = getAccessToken();
      try {
        const result = await completeMicrosoftFederated(
          { code, state },
          { auth: Boolean(existingToken) },
        );
        if (isTokenResponse(result)) {
          storeSessionToken(result.access_token);
          const currentUser = await fetchCurrentUser();
          track("user_login_succeeded", {
            auth_method: "microsoft",
            role: currentUser.role,
          });
          router.replace("/");
          return;
        }
        router.replace("/account/profile");
      } catch (error) {
        if (error instanceof ApiError) {
          track("user_login_failed", {
            failure_reason:
              error.status === 401
                ? "unlinked_microsoft_identity"
                : "federated_callback_rejected",
          });
          setErrorMessage(error.message);
          return;
        }
        setErrorMessage(GENERIC_ERROR_MESSAGE);
      }
    };

    void run();
  }, [router, code, state]);

  const visibleError =
    errorMessage ??
    (missingCallbackParams
      ? "Microsoft sign-in did not return a complete response."
      : null);

  if (visibleError) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <h1>Microsoft sign-in</h1>
          <ErrorRecovery message={visibleError} homeHref="/login" />
        </div>
      </div>
    );
  }

  return (
    <div className="auth-loading" role="status">
      Completing Microsoft sign-in…
    </div>
  );
};

export default function MicrosoftCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="auth-loading" role="status">
          Completing Microsoft sign-in…
        </div>
      }
    >
      <MicrosoftCallbackHandler />
    </Suspense>
  );
};
