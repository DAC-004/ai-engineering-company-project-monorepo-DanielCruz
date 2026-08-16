"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { logout } from "@/lib/auth/session";

type AppShellProps = {
  children: ReactNode;
};

export const AppShell = ({ children }: AppShellProps) => {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
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
        <nav className="app-nav" aria-label="Application">
          <Link
            href="/"
            className={pathname === "/" ? "app-nav__link is-active" : "app-nav__link"}
          >
            Home
          </Link>
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
            Summary
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
