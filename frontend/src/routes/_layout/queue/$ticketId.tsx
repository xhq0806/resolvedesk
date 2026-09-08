import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import {
  PendingTicketDetail,
  TicketDetailPage,
} from "@/components/Tickets/TicketDetailPage"
import { requireRoles } from "@/lib/routeGuards"

export const Route = createFileRoute("/_layout/queue/$ticketId")({
  component: AgentTicketDetailRoute,
  beforeLoad: requireRoles({ allowed: ["AGENT"], redirectTo: "/" }),
  head: () => ({
    meta: [{ title: "Ticket details - FastAPI Template" }],
  }),
})

function AgentTicketDetailRoute() {
  const { ticketId } = Route.useParams()

  return (
    <Suspense fallback={<PendingTicketDetail />}>
      <TicketDetailPage ticketId={ticketId} view="agent" />
    </Suspense>
  )
}
