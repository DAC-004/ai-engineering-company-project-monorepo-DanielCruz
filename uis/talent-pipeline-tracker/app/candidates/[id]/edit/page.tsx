import { EditCandidatePage } from "@/components/candidates/EditCandidatePage";

interface EditCandidateRouteProps {
  params: Promise<{ id: string }>;
}

export default async function EditCandidateRoute({
  params,
}: EditCandidateRouteProps) {
  const { id } = await params;

  return <EditCandidatePage candidateId={id} />;
}
