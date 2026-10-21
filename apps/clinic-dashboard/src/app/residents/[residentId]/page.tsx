import { CareResidentDetail } from "@/features/workspace";

export default async function ResidentPage({ params }: { params: Promise<{ residentId: string }> }) {
  const { residentId } = await params;
  return <CareResidentDetail residentId={residentId} />;
}
