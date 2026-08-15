import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm";

export default function ForgotPasswordPage() {
  return (
    <div className="auth-screen">
      <div className="auth-card">
        <p className="eyebrow">HealthCore Digital</p>
        <h1>Forgot password</h1>
        <p className="auth-lede">
          Enter the email for your account. If it is registered, we will send a
          one-time reset link.
        </p>
        <ForgotPasswordForm />
      </div>
    </div>
  );
}
