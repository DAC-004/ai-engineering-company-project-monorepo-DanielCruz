"use client";

import { useEffect, useState } from "react";

import { ErrorRecovery } from "@/components/auth/ErrorRecovery";
import {
  fetchMicrosoftLinkStatus,
  startMicrosoftFederated,
  unlinkMicrosoft,
  type FederatedStatusResponse,
} from "@/lib/auth/federated";
import { ApiError } from "@/lib/auth/types";
import { GENERIC_ERROR_MESSAGE } from "@/lib/auth/userFacingError";

export const FederatedLinkControls = () => {
  const [status, setStatus] = useState<FederatedStatusResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoadError(null);
      try {
        const nextStatus = await fetchMicrosoftLinkStatus();
        if (!cancelled) {
          setStatus(nextStatus);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (error instanceof ApiError && error.status === 401) {
          return;
        }
        setLoadError(
          error instanceof ApiError ? error.message : GENERIC_ERROR_MESSAGE,
        );
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const handleLink = async () => {
    setActionError(null);
    setIsBusy(true);
    try {
      const started = await startMicrosoftFederated("link", { auth: true });
      window.location.assign(started.authorization_url);
    } catch (error) {
      setActionError(
        error instanceof ApiError ? error.message : GENERIC_ERROR_MESSAGE,
      );
      setIsBusy(false);
    }
  };

  const handleUnlink = async () => {
    if (!status) {
      return;
    }
    if (!status.can_unlink) {
      setActionError(
        status.unlink_blocked_reason ??
          "Cannot unlink the last remaining access method",
      );
      return;
    }
    setActionError(null);
    setIsBusy(true);
    try {
      const nextStatus = await unlinkMicrosoft();
      setStatus(nextStatus);
    } catch (error) {
      setActionError(
        error instanceof ApiError ? error.message : GENERIC_ERROR_MESSAGE,
      );
    } finally {
      setIsBusy(false);
    }
  };

  if (loadError) {
    return (
      <ErrorRecovery
        message={loadError}
        onRetry={() => setReloadKey((current) => current + 1)}
      />
    );
  }

  if (!status) {
    return (
      <p className="field-hint" role="status">
        Loading Microsoft sign-in…
      </p>
    );
  }

  return (
    <section className="federated-link-panel" aria-labelledby="federated-link-heading">
      <h2 id="federated-link-heading">Microsoft sign-in</h2>
      <p>
        Linking is available only on this profile after a traditional staff sign-in.
        Microsoft login never creates an account.
      </p>
      {status.linked && status.link ? (
        <p className="field-hint">
          Linked Microsoft identity snapshot: {status.link.email_at_link_time ?? "stored"}
        </p>
      ) : (
        <p className="field-hint">Microsoft is not linked on this profile.</p>
      )}
      {!status.can_unlink && status.linked ? (
        <p className="federated-link-warning" role="status">
          Unlinking Microsoft would remove your last access method. Add a password
          or another approved method first. The API will refuse this unlink.
        </p>
      ) : null}
      {actionError ? <ErrorRecovery message={actionError} /> : null}
      <div className="action-row">
        {status.linked ? (
          <button
            type="button"
            className="btn-danger"
            onClick={() => {
              void handleUnlink();
            }}
            disabled={isBusy}
          >
            {isBusy ? "Working…" : "Unlink Microsoft"}
          </button>
        ) : (
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              void handleLink();
            }}
            disabled={isBusy}
          >
            {isBusy ? "Redirecting…" : "Link Microsoft"}
          </button>
        )}
      </div>
    </section>
  );
};
