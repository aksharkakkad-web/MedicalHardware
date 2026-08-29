import { MonitoringSetup } from "@/features/setup/monitoring-setup";

export default async function MonitoringSetupPage({
  params,
}: Readonly<{ params: Promise<{ residentId: string }> }>) {
  const { residentId } = await params;
  return <MonitoringSetup residentId={residentId} />;
}
