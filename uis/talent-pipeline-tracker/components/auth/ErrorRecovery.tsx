import Link from "next/link";

import { SUPPORT_EMAIL } from "@/lib/auth/userFacingError";

type ErrorRecoveryProps = {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  homeHref?: string;
  signInHref?: string;
};

export const ErrorRecovery = ({
  message,
  onRetry,
  retryLabel = "Try again",
  homeHref,
  signInHref,
}: ErrorRecoveryProps) => (
  <div className="form-error error-recovery" role="alert">
    <p>{message}</p>
    <p className="error-recovery__help">
      If this continues, contact support at{" "}
      <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
    </p>
    {onRetry || homeHref || signInHref ? (
      <div className="error-recovery__actions">
        {onRetry ? (
          <button type="button" className="btn-secondary" onClick={onRetry}>
            {retryLabel}
          </button>
        ) : null}
        {homeHref ? (
          <Link href={homeHref} className="btn-secondary">
            Home
          </Link>
        ) : null}
        {signInHref ? (
          <Link href={signInHref} className="btn-secondary">
            Sign in
          </Link>
        ) : null}
      </div>
    ) : null}
  </div>
);
