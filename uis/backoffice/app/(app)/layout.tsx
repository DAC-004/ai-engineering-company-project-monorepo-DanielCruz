import { AuthGuard } from "@/components/auth/AuthGuard";
import { AppShell } from "@/components/auth/AppShell";
import type { ReactNode } from "react";

/**
 * Layout for authenticated application views.
 * Public routes (/login, /register) live outside this group and are not guarded.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}
