"use client";

import Link from "next/link";

import { useCurrentUser } from "@/lib/auth/CurrentUserContext";
import {
  canCreateDepartmentRecord,
  canManageAccess,
} from "@/lib/auth/capabilities";

/**
 * Main authenticated view after login/registration.
 * Unauthenticated visitors are redirected to /login by the parent AuthGuard.
 */
export default function HomePage() {
  const currentUser = useCurrentUser();
  const canCreate = canCreateDepartmentRecord(currentUser?.role);
  const isAccessAdmin = canManageAccess(currentUser?.role);

  return (
    <section className="home-panel">
      <p className="eyebrow">Authenticated session</p>
      <h1>Welcome to HealthCore Internal Workspace</h1>
      <p className="home-lede">
        Signed in as {currentUser?.email}. Role {currentUser?.role}
        {currentUser?.department_name ? ` · ${currentUser.department_name}` : ""}.
      </p>
      <div className="home-actions">
        {canCreate ? (
        <Link href="/incidents/new" className="btn-primary">
          Register incident
        </Link>
        ) : null}
        <Link href="/incidents" className="btn-secondary">
          View incidents
        </Link>
        <Link href="/incidents/summary" className="btn-secondary">
          Incident summary
        </Link>
        <Link href="/incident-analysis" className="btn-secondary">
          Incident analysis
        </Link>
        <Link href="/backoffice/inventory/products" className="btn-secondary">
          Medical supplies
        </Link>
        {canCreate ? (
        <Link href="/backoffice/inventory/orders/inbound" className="btn-secondary">
          Log supply delivery
        </Link>
        ) : null}
        {canCreate ? (
        <Link href="/backoffice/inventory/orders/outbound" className="btn-secondary">
          Log supply consumption
        </Link>
        ) : null}
        <Link href="/backoffice/inventory/orders" className="btn-secondary">
          Supply movements
        </Link>
        <Link href="/backoffice/suppliers" className="btn-secondary">
          Supplier directory
        </Link>
        <Link href="/backoffice/rfp" className="btn-secondary">
          RFP intake
        </Link>
        <Link href="/backoffice/knowledge" className="btn-secondary">
          Knowledge assistant
        </Link>
        <Link href="/backoffice/reporting" className="btn-secondary">
          Clinic supply report
        </Link>
        <Link href="/backoffice/internal-reports" className="btn-secondary">
          Internal reports
        </Link>
        {isAccessAdmin ? (
        <Link href="/backoffice/access" className="btn-secondary">
          Roles and departments
        </Link>
        ) : null}
        {isAccessAdmin ? (
        <Link href="/backoffice/access/create" className="btn-secondary">
          Create account
        </Link>
        ) : null}
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
