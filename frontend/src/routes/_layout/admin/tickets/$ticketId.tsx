import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import {
  PendingTicketDetail,
  TicketDetailPage,
} from "@/components/Tickets/TicketDetailPage"
import { requireRoles } from "@/lib/routeGuards"

export const Route = createFileRoute("/_layout/admin/tickets/$ticketId")({
  component: AdminTicketDetailRoute,
  beforeLoad: requireRoles({ allowed: ["ADMIN"], redirectTo: "/" }),
  head: () => ({
    meta: [{ title: "Ticket details - FastAPI Template" }],
  }),
})

function AdminTicketDetailRoute() {
  const { ticketId } = Route.useParams()

  return (
    <Suspense fallback={<PendingTicketDetail />}>
      <TicketDetailPage ticketId={ticketId} view="admin" />
    </Suspense>
  )
}
