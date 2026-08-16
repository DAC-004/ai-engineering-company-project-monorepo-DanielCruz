import Link from "next/link";

/**
 * Main authenticated view after login/registration.
 * Unauthenticated visitors are redirected to /login by the parent AuthGuard.
 */
export default function HomePage() {
  return (
    <section className="home-panel">
      <p className="eyebrow">Authenticated session</p>
      <h1>Welcome to HealthCore Internal Workspace</h1>
      <p className="home-lede">
        You are signed in with a JWT stored in localStorage. Protected API calls from this
        application attach that token as Authorization: Bearer.
      </p>
      <div className="home-actions">
        <Link href="/incidents/new" className="btn-primary">
          Register incident
        </Link>
        <Link href="/incidents" className="btn-secondary">
          View incidents
        </Link>
        <Link href="/incidents/summary" className="btn-secondary">
          Summary
        </Link>
        <Link href="/account/profile" className="btn-secondary">
          Manage profile
        </Link>
      </div>
    </section>
  );
}
