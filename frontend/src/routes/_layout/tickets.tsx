import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"
import { DataTable } from "@/components/Common/DataTable"
import PendingTickets from "@/components/Pending/PendingTickets"
import { CreateTicketDialog } from "@/components/Tickets/CreateTicketDialog"
import { ticketColumns } from "@/components/Tickets/TicketColumns"
import { TicketFilters } from "@/components/Tickets/TicketFilters"
import { requireRoles } from "@/lib/routeGuards"
import {
  normalizeTicketListFilters,
  type TicketFilterChange,
  ticketFiltersToSearch,
  ticketListQueryOptions,
  ticketSearchSchema,
  ticketSearchToFilters,
} from "@/lib/ticketQueries"

export const Route = createFileRoute("/_layout/tickets")({
  component: TicketsPage,
  validateSearch: ticketSearchSchema,
  beforeLoad: requireRoles({ allowed: ["CUSTOMER"], redirectTo: "/" }),
  head: () => ({
    meta: [{ title: "My tickets - FastAPI Template" }],
  }),
})

function TicketsTableContent() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const filters = ticketSearchToFilters(search)
  const { data: tickets, isFetching } = useSuspenseQuery(
    ticketListQueryOptions("customer", filters),
  )

  const updateFilters = (change: TicketFilterChange) => {
    const nextFilters = normalizeTicketListFilters({ ...filters, ...change })
    void navigate({ search: ticketFiltersToSearch(nextFilters) })
  }

  return (
    <DataTable
      columns={ticketColumns}
      data={tickets.data}
      toolbar={<TicketFilters filters={filters} onChange={updateFilters} />}
      emptyState="No tickets match the current filters."
      isFetching={isFetching}
      pagination={{
        pageIndex: filters.page - 1,
        pageSize: filters.pageSize,
        totalCount: tickets.count,
        onPageChange: (pageIndex) => updateFilters({ page: pageIndex + 1 }),
        onPageSizeChange: (pageSize) => updateFilters({ page: 1, pageSize }),
      }}
    />
  )
}

function TicketsTable() {
  return (
    <Suspense fallback={<PendingTickets />}>
      <TicketsTableContent />
    </Suspense>
  )
}

function TicketsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Customer workspace
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            My tickets
          </h1>
          <p className="mt-1 text-muted-foreground">
            Track requests, updates, and support conversations in one place.
          </p>
        </div>
        <CreateTicketDialog />
      </div>
      <TicketsTable />
    </div>
  )
}
