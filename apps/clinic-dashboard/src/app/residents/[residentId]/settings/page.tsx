import { ResidentSettings } from "@/features/resident-settings/resident-settings";

export default async function ResidentSettingsPage({
  params,
}: Readonly<{ params: Promise<{ residentId: string }> }>) {
  const { residentId } = await params;
  return <ResidentSettings residentId={residentId} />;
}
