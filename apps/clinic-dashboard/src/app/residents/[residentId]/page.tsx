import { ResidentDetail } from "@/features/residents/resident-detail";

export default async function ResidentPage({ params }: { params: Promise<{ residentId: string }> }) {
  const { residentId } = await params;
  return <ResidentDetail residentId={residentId} />;
}
