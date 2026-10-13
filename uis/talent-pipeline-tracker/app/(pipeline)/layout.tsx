import { AuthGuard } from "@/components/auth/AuthGuard";
import { AppShell } from "@/components/auth/AppShell";
import { AppHeader } from "@/components/layout/AppHeader";
import { PageContainer } from "@/components/layout/PageContainer";
import type { ReactNode } from "react";

/**
 * Talent pipeline routes share the authenticated AppShell so staff keep the
 * same session, return navigation, and layout as the rest of the workspace.
 * Milestone 3 candidate chrome (AppHeader) remains inside the shell.
 * These pages still call the 4Geeks tracker API for candidate records.
 */
export default function PipelineLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>
        <div className="pipeline-shell flex min-h-screen flex-col bg-slate-50 text-hc-ink">
          <AppHeader />
          <PageContainer>{children}</PageContainer>
        </div>
      </AppShell>
    </AuthGuard>
  );
}
