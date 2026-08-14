import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <div className="auth-screen">
      <div className="auth-card">
        <p className="eyebrow">HealthCore Digital</p>
        <h1>Sign in</h1>
        <p className="auth-lede">
          Authenticate against the HealthCore API. Your JWT is stored in localStorage
          for protected requests.
        </p>
        <LoginForm />
      </div>
    </div>
  );
}
