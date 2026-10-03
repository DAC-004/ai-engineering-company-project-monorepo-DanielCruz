import { Suspense } from "react";

import { CandidateListPage } from "@/components/candidates/CandidateListPage";
import { LoadingState } from "@/components/ui/LoadingState";

export default function CandidateListRoute() {
  return (
    <Suspense fallback={<LoadingState message="Loading pipeline..." />}>
      <CandidateListPage />
    </Suspense>
  );
}
