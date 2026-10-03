import { Suspense } from "react";

import { CandidateDetailPage } from "@/components/candidates/CandidateDetailPage";
import { LoadingState } from "@/components/ui/LoadingState";

interface CandidatePageProps {
  params: Promise<{ id: string }>;
}

export default async function CandidatePage({ params }: CandidatePageProps) {
  const { id } = await params;

  return (
    <Suspense fallback={<LoadingState message="Loading candidate profile..." />}>
      <CandidateDetailPage candidateId={id} />
    </Suspense>
  );
}
