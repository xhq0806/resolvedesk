import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import {
  PendingTicketDetail,
  TicketDetailPage,
} from "@/components/Tickets/TicketDetailPage"
import { requireRoles } from "@/lib/routeGuards"

export const Route = createFileRoute("/_layout/tickets/$ticketId")({
  component: CustomerTicketDetailRoute,
  beforeLoad: requireRoles({ allowed: ["CUSTOMER"], redirectTo: "/" }),
  head: () => ({
    meta: [{ title: "Ticket details - ResolveDesk" }],
  }),
})

function CustomerTicketDetailRoute() {
  const { ticketId } = Route.useParams()

  return (
    <Suspense fallback={<PendingTicketDetail />}>
      <TicketDetailPage ticketId={ticketId} view="customer" />
    </Suspense>
  )
}
