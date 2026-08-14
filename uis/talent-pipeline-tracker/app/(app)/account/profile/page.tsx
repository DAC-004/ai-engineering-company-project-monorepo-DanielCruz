import { ProfileForm } from "@/components/auth/ProfileForm";

export default function ProfilePage() {
  return (
    <section className="home-panel">
      <p className="eyebrow">Account</p>
      <h1>Profile</h1>
      <p className="home-lede">
        Email is loaded from the User via GET /auth/me. Name, phone, and address come from
        the linked Profile and can be updated with PUT /profiles/me.
      </p>
      <ProfileForm />
    </section>
  );
}
