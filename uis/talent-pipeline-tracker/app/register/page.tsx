import { RegisterForm } from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  return (
    <div className="auth-screen">
      <div className="auth-card">
        <p className="eyebrow">HealthCore Digital</p>
        <h1>Create account</h1>
        <p className="auth-lede">
          Registers with POST /users, then signs in with POST /auth/login so the session
          is ready immediately.
        </p>
        <RegisterForm />
      </div>
    </div>
  );
}
