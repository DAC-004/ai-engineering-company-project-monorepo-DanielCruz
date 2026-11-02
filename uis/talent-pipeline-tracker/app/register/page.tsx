import Link from "next/link";

export default function RegisterPage() {
  return (
    <div className="auth-screen">
      <div className="auth-card">
        <p className="eyebrow">HealthCore Digital</p>
        <h1>Account creation is not public</h1>
        <p className="auth-lede">
          User accounts are created by an administrator. Public registration is
          disabled.
        </p>
        <p className="auth-switch">
          <Link href="/login">Sign in</Link>
        </p>
        <p className="auth-switch">
          <Link href="/forgot-password">Forgot your password?</Link>
        </p>
      </div>
    </div>
  );
}
