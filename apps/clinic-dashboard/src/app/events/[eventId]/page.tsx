import { CareEventDetail } from "@/features/workspace";

export default async function EventPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = await params;
  return <CareEventDetail eventId={eventId} />;
}
