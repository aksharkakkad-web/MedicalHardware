import { UpdateDetail } from "@/features/updates/update-detail";

export default async function UpdatePage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = await params;
  return <UpdateDetail eventId={eventId} />;
}
