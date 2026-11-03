"use client";

import { useSearchParams } from "next/navigation";

/**
 * Isolated so useSearchParams does not force the whole login form to defer hydration.
 */
export const LoginResetNotice = () => {
  const searchParams = useSearchParams();
  const resetSuccessMessage =
    searchParams.get("reset") === "success"
      ? "Password updated. Sign in with your new password."
      : null;

  if (!resetSuccessMessage) {
    return null;
  }

  return (
    <p className="form-success" role="status">
      {resetSuccessMessage}
    </p>
  );
};
