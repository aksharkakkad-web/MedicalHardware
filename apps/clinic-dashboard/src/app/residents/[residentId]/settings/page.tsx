import { ResidentAdministration } from "@/features/workspace-admin";

export default async function ResidentSettingsPage({ params }: { params: Promise<{ residentId: string }> }) {
  const { residentId } = await params;
  return <ResidentAdministration residentId={residentId} />;
}
