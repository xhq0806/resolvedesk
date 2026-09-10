import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { DataTable } from "@/components/Common/DataTable"
import PendingTickets from "@/components/Pending/PendingTickets"
import { createTicketColumns } from "@/components/Tickets/TicketColumns"
import { TicketFilters } from "@/components/Tickets/TicketFilters"
import {
  activeAgentsQueryOptions,
  normalizeTicketListFilters,
  type TicketFilterChange,
  ticketFiltersToSearch,
  ticketListQueryOptions,
  ticketSearchSchema,
  ticketSearchToFilters,
} from "@/lib/ticketQueries"

// Admin 工单列表复用服务端分页和 URL 筛选，保证全局管理页刷新后状态不丢失。by AI.Coding
export const Route = createFileRoute("/_layout/admin/tickets/")({
  component: AdminTicketsPage,
  validateSearch: ticketSearchSchema,
  head: () => ({
    meta: [{ title: "All tickets - ResolveDesk" }],
  }),
})

function AdminTicketsPage() {
  return (
    <Suspense fallback={<PendingTickets />}>
      <AdminTicketsContent />
    </Suspense>
  )
}

function AdminTicketsContent() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const filters = ticketSearchToFilters(ticketSearchSchema.parse(search))
  const { data: tickets, isFetching } = useSuspenseQuery(
    ticketListQueryOptions("admin", filters),
  )
  const { data: assignees } = useSuspenseQuery(activeAgentsQueryOptions())

  const updateFilters = (change: TicketFilterChange) => {
    const nextFilters = normalizeTicketListFilters({ ...filters, ...change })
    void navigate({ search: ticketFiltersToSearch(nextFilters) })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Admin workspace
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          All tickets
        </h1>
        <p className="mt-1 text-muted-foreground">
          Review, assign, and resolve every customer request.
        </p>
      </div>
      <DataTable
        columns={createTicketColumns("/admin/tickets/$ticketId")}
        data={tickets.data}
        toolbar={
          <TicketFilters
            filters={filters}
            onChange={updateFilters}
            assignees={assignees}
          />
        }
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
    </div>
  )
}
