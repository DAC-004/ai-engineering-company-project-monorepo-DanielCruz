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
        <Link href="/account/profile" className="btn-primary">
          Manage profile
        </Link>
      </div>
    </section>
  );
}
