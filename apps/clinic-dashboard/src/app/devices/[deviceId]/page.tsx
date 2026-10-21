import { ScopedDeviceDetail } from "@/components/workspace-access/workspace-access";

export default async function DevicePage({ params }: { params: Promise<{ deviceId: string }> }) {
  const { deviceId } = await params;
  return <ScopedDeviceDetail deviceId={deviceId} />;
}
