"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { logout } from "@/lib/auth/session";
import { track } from "@/src/services/telemetry";

type AppShellProps = {
  children: ReactNode;
};

export const AppShell = ({ children }: AppShellProps) => {
  const pathname = usePathname();
  const router = useRouter();

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
            href="/backoffice/inventory/products"
            className={
              pathname.startsWith("/backoffice/inventory/products")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Medical supplies
          </Link>
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
            href="/account/profile"
            className={
              pathname.startsWith("/account/profile")
                ? "app-nav__link is-active"
                : "app-nav__link"
            }
          >
            Profile
          </Link>
          <button type="button" className="btn-secondary" onClick={handleLogout}>
            Log out
          </button>
        </nav>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
};
