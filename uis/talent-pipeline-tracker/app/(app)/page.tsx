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
          Incident summary
        </Link>
        <Link href="/backoffice/inventory/products" className="btn-secondary">
          Medical supplies
        </Link>
        <Link href="/backoffice/inventory/orders/inbound" className="btn-secondary">
          Log supply delivery
        </Link>
        <Link href="/backoffice/inventory/orders/outbound" className="btn-secondary">
          Log supply consumption
        </Link>
        <Link href="/backoffice/inventory/orders" className="btn-secondary">
          Supply movements
        </Link>
        <Link href="/backoffice/suppliers" className="btn-secondary">
          Supplier directory
        </Link>
        <Link href="/backoffice/knowledge" className="btn-secondary">
          Knowledge assistant
        </Link>
        <Link href="/account/profile" className="btn-secondary">
          Manage profile
        </Link>
        <Link href="/candidates" className="btn-secondary">
          Talent pipeline
        </Link>
        <Link href="/account/change-password" className="btn-secondary">
          Change password
        </Link>
      </div>
    </section>
  );
}
