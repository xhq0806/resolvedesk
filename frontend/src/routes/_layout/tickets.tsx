import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Outlet, useMatch } from "@tanstack/react-router"
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
  component: TicketsRoute,
  validateSearch: ticketSearchSchema,
  beforeLoad: requireRoles({ allowed: ["CUSTOMER"], redirectTo: "/" }),
  head: () => ({
    meta: [{ title: "我的工单 - ResolveDesk" }],
  }),
})

function TicketsRoute() {
  const detailMatch = useMatch({
    from: "/_layout/tickets/$ticketId",
    shouldThrow: false,
  })

  return detailMatch ? <Outlet /> : <TicketsPage />
}

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
      emptyState="没有符合当前筛选条件的工单。"
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
            客户工作台
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            我的工单
          </h1>
          <p className="mt-1 text-muted-foreground">
            在一个页面跟踪请求、进展和客服沟通。
          </p>
        </div>
        <CreateTicketDialog />
      </div>
      <TicketsTable />
    </div>
  )
}
