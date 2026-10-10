import { Suspense } from "react";

import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";

export default function ResetPasswordPage() {
  return (
    <div className="auth-screen">
      <div className="auth-card">
        <p className="eyebrow">HealthCore Digital</p>
        <h1>Reset password</h1>
        <p className="auth-lede">
          Choose a new password using the token from your reset email link.
        </p>
        <Suspense fallback={<p className="auth-loading">Loading reset form…</p>}>
          <ResetPasswordForm />
        </Suspense>
      </div>
    </div>
  );
}
