import { EventDetail } from "@/features/events/event-detail";

export default async function EventPage({
  params,
}: Readonly<{ params: Promise<{ eventId: string }> }>) {
  const { eventId } = await params;
  return <EventDetail eventId={eventId} />;
}
