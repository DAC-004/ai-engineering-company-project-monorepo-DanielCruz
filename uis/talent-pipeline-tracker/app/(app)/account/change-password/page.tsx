import { ChangePasswordForm } from "@/components/auth/ChangePasswordForm";

export default function ChangePasswordPage() {
  return (
    <section className="home-panel">
      <p className="eyebrow">Account</p>
      <h1>Change password</h1>
      <p className="home-lede">
        Verify your current password, then set a new one. The confirmation field
        must match before the API is called.
      </p>
      <ChangePasswordForm />
    </section>
  );
}
