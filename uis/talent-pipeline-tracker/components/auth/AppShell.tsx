"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { logout } from "@/lib/auth/session";
import { useCurrentUser } from "@/lib/auth/CurrentUserContext";
import {
  canCreateDepartmentRecord,
  canManageAccess,
} from "@/lib/auth/capabilities";
import { RfpArrivalNotifications } from "@/components/rfp/RfpArrivalNotifications";
import { track } from "@/src/services/telemetry";

type AppShellProps = {
  children: ReactNode;
};

export const AppShell = ({ children }: AppShellProps) => {
  const pathname = usePathname();
  const router = useRouter();
  const currentUser = useCurrentUser();
  const canCreate = canCreateDepartmentRecord(currentUser?.role);
  const isAccessAdmin = canManageAccess(currentUser?.role);

  const handleLogout = () => {
    track("user_logout_completed", { logout_method: "user_initiated" });
    logout();
    router.replace("/login");
  };

  return (
    <div className="app-frame">
      <header className="app-header">
        <div className="app-header__brand">
          <p className="eyebrow">HealthCore Digital</p>
          <Link href="/" className="app-header__title">
            Internal Workspace
          </Link>
        </div>
        <nav className="app-nav" aria-label="Workspace">
          <Link
            href="/"
            className={pathname === "/" ? "app-nav__link is-active" : "app-nav__link"}
          >
            Home
          </Link>
          <Link
            href="/candidates"
            className={
              pathname.startsWith("/candidates") ? "app-nav__link is-active" : "app-nav__link"
            }
          >
            Talent pipeline
          </Link>
          {canCreate ? (
          <Link
            href="/incidents/new"
            className={
              pathname.startsWith("/incidents/new")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Register incident
          </Link>
          ) : null}
          <Link
            href="/incidents"
            className={
              pathname === "/incidents" ? "app-nav__link is-active" : "app-nav__link"
            }
          >
            Incidents
          </Link>
          <Link
            href="/incidents/summary"
            className={
              pathname.startsWith("/incidents/summary")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Incident summary
          </Link>
          <Link
            href="/incident-analysis"
            className={
              pathname.startsWith("/incident-analysis")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Incident analysis
          </Link>
          <Link
            href="/backoffice/inventory/products"
            className={
              pathname.startsWith("/backoffice/inventory/products")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Medical supplies
          </Link>
          {canCreate ? (
          <Link
            href="/backoffice/inventory/orders/inbound"
            className={
              pathname.startsWith("/backoffice/inventory/orders/inbound")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Supply delivery
          </Link>
          ) : null}
          {canCreate ? (
          <Link
            href="/backoffice/inventory/orders/outbound"
            className={
              pathname.startsWith("/backoffice/inventory/orders/outbound")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Supply consumption
          </Link>
          ) : null}
          <Link
            href="/backoffice/inventory/orders"
            className={
              pathname === "/backoffice/inventory/orders"
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Supply movements
          </Link>
          <Link
            href="/backoffice/suppliers"
            className={
              pathname.startsWith("/backoffice/suppliers")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Supplier directory
          </Link>
          <Link
            href="/backoffice/rfp"
            className={
              pathname.startsWith("/backoffice/rfp")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            RFP intake
          </Link>
          <Link
            href="/backoffice/knowledge"
            className={
              pathname.startsWith("/backoffice/knowledge")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Knowledge assistant
          </Link>
          <Link
            href="/backoffice/reporting"
            className={
              pathname.startsWith("/backoffice/reporting")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Clinic supply report
          </Link>
          <Link
            href="/backoffice/internal-reports"
            className={
              pathname.startsWith("/backoffice/internal-reports")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Internal reports
          </Link>
          {isAccessAdmin ? (
          <Link
            href="/backoffice/access"
            className={
              pathname === "/backoffice/access"
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Roles and departments
          </Link>
          ) : null}
          {isAccessAdmin ? (
          <Link
            href="/backoffice/access/create"
            className={
              pathname.startsWith("/backoffice/access/create")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Create account
          </Link>
          ) : null}
          <Link
            href="/account/profile"
            className={
              pathname.startsWith("/account/profile")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Profile
          </Link>
          <Link
            href="/account/change-password"
            className={
              pathname.startsWith("/account/change-password")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Change password
          </Link>
          <button type="button" className="btn-secondary" onClick={handleLogout}>
            Log out
          </button>
        </nav>
      </header>
      <main className="app-main">
        <RfpArrivalNotifications />
        {children}
      </main>
    </div>
  );
};
