import { AppHeader } from "@/components/layout/AppHeader";
import { PageContainer } from "@/components/layout/PageContainer";
import type { ReactNode } from "react";

/**
 * Chrome for the Milestone 3 candidate pipeline.
 * These routes stay outside the authenticated (app) group because they call
 * the 4Geeks tracker API rather than the HealthCore JWT API. The list lives
 * at /candidates so it does not collide with app/(app)/page.tsx at /.
 */
export default function PipelineLayout({ children }: { children: ReactNode }) {
  return (
    <div className="pipeline-shell flex min-h-screen flex-col bg-slate-50 text-hc-ink">
      <AppHeader />
      <PageContainer>{children}</PageContainer>
    </div>
  );
}
