import { ScopedMonitoringSetup } from "@/components/workspace-access/workspace-access";

export default async function MonitoringSetupPage({ params }: { params: Promise<{ residentId: string }> }) {
  const { residentId } = await params;
  return <ScopedMonitoringSetup residentId={residentId} />;
}
