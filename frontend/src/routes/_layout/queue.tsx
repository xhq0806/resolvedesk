import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import { Headset, Inbox, UserRound, UsersRound } from "lucide-react"
import { Suspense, useMemo } from "react"
import { z } from "zod"

import { TicketsService } from "@/client"
import { createAgentQueueColumns } from "@/components/Tickets/AgentQueueColumns"
import { TicketFilters } from "@/components/Tickets/TicketFilters"
import PendingTickets from "@/components/Pending/PendingTickets"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"
import { requireRoles } from "@/lib/routeGuards"
import {
  invalidateTicketQueries,
  normalizeTicketListFilters,
  ticketListQueryOptions,
  ticketStatisticsQueryOptions,
  type TicketFilterChange,
  type TicketListFilters,
} from "@/lib/ticketQueries"
import { handleError } from "@/utils"
import useCustomToast from "@/hooks/useCustomToast"
import { DataTable } from "@/components/Common/DataTable"

const queueViewValues = ["unassigned", "mine", "waiting"] as const
type QueueView = (typeof queueViewValues)[number]

const queueSearchSchema = z.object({
  view: z.enum(queueViewValues).catch("unassigned"),
  page: z.coerce.number().int().min(1).catch(1),
  pageSize: z.coerce.number().int().min(1).max(100).catch(25),
  query: z.string().trim().catch(""),
  priority: z.enum(["LOW", "MEDIUM", "HIGH", "URGENT"]).optional(),
  category: z
    .enum(["ACCOUNT", "BILLING", "PRODUCT", "BUG", "FEATURE_REQUEST", "OTHER"])
    .optional(),
})

export const Route = createFileRoute("/_layout/queue")({
  component: QueuePage,
  validateSearch: queueSearchSchema,
  beforeLoad: requireRoles({ allowed: ["AGENT"], redirectTo: "/" }),
  head: () => ({
    meta: [{ title: "Service queue - FastAPI Template" }],
  }),
})

const isQueueView = (value: string): value is QueueView =>
  queueViewValues.includes(value as QueueView)

type QueueFilterSource = Partial<
  Pick<
    TicketListFilters,
    "page" | "pageSize" | "query" | "status" | "priority" | "category" | "assigneeId"
  >
>

const getQueueFilters = (
  search: QueueFilterSource,
  view: QueueView,
  userId: string,
): TicketListFilters =>
  normalizeTicketListFilters({
    ...search,
    status:
      view === "unassigned"
        ? "OPEN"
        : view === "waiting"
          ? "WAITING_FOR_CUSTOMER"
          : null,
    assigneeId: view === "unassigned" ? null : userId,
  })

const getQueueSearch = (filters: TicketListFilters, view: QueueView) => ({
  view,
  page: filters.page,
  pageSize: filters.pageSize,
  query: filters.query,
  priority: filters.priority ?? undefined,
  category: filters.category ?? undefined,
})

const isClaimConflict = (error: unknown) => {
  if (!isAxiosError(error) || error.response?.status !== 409) return false

  const payload = error.response.data
  return (
    typeof payload === "object" &&
    payload !== null &&
    "code" in payload &&
    payload.code === "TICKET_ALREADY_CLAIMED"
  )
}

function QueuePage() {
  return (
    <Suspense fallback={<PendingTickets />}>
      <AgentQueueContent />
    </Suspense>
  )
}

function AgentQueueContent() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data: statistics } = useSuspenseQuery(ticketStatisticsQueryOptions())
  const view = search.view

  const selectView = (value: string) => {
    if (!isQueueView(value)) return
    void navigate({ search: { ...search, view: value, page: 1 } })
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Operations / Agent desk
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Service queue
          </h1>
          <p className="mt-1 text-muted-foreground">
            Triage incoming requests and keep customer work moving.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Headset className="h-4 w-4" />
          <span>Agent workspace</span>
        </div>
      </div>

      <Tabs value={view} onValueChange={selectView} className="gap-5">
        <TabsList className="grid h-auto w-full grid-cols-1 p-1 sm:grid-cols-3">
          <TabsTrigger value="unassigned" className="h-10 justify-start px-4 sm:justify-center">
            <Inbox className="h-4 w-4" />
            Unassigned queue
            <Badge variant="secondary" className="ml-1">
              {statistics.unassigned_count}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="mine" className="h-10 justify-start px-4 sm:justify-center">
            <UserRound className="h-4 w-4" />
            My tickets
            <Badge variant="secondary" className="ml-1">
              {statistics.assigned_to_me_count}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="waiting" className="h-10 justify-start px-4 sm:justify-center">
            <UsersRound className="h-4 w-4" />
            Waiting for customer
            <Badge variant="secondary" className="ml-1">
              {statistics.waiting_for_customer_count}
            </Badge>
          </TabsTrigger>
        </TabsList>
        <QueueTable view={view} />
      </Tabs>
    </div>
  )
}

function QueueTable({ view }: { view: QueueView }) {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { user: currentUser } = useAuth()
  const client = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const userId = currentUser?.id ?? ""
  const filters = getQueueFilters(search, view, userId)
  const scope = view === "unassigned" ? "agent-queue" : "agent-mine"
  const { data: tickets, isFetching } = useSuspenseQuery(
    ticketListQueryOptions(scope, filters),
  )

  const updateFilters = (change: TicketFilterChange) => {
    const nextFilters = getQueueFilters(
      normalizeTicketListFilters({ ...filters, ...change }),
      view,
      userId,
    )
    void navigate({ search: getQueueSearch(nextFilters, view) })
  }

  const claimMutation = useMutation({
    mutationFn: (ticketId: string) =>
      TicketsService.claimTicket({ path: { ticket_id: ticketId } }),
    onSuccess: async (_response, ticketId) => {
      await invalidateTicketQueries(client, { ticketId })
      showSuccessToast("Ticket claimed and added to your work queue.")
    },
    onError: async (error: Error, ticketId) => {
      if (isClaimConflict(error)) {
        await invalidateTicketQueries(client, { ticketId })
        showErrorToast("Another agent claimed this ticket. The queue was refreshed.")
        return
      }

      handleError.call(showErrorToast, error)
    },
  })

  const columns = useMemo(
    () =>
      createAgentQueueColumns({
        onClaim: (ticketId) => claimMutation.mutate(ticketId),
        claimingTicketId: claimMutation.isPending
          ? claimMutation.variables
          : undefined,
      }),
    [claimMutation.isPending, claimMutation.variables],
  )

  return (
    <DataTable
      columns={columns}
      data={tickets.data}
      toolbar={
        <TicketFilters
          filters={filters}
          onChange={updateFilters}
          showStatus={false}
        />
      }
      emptyState={
        view === "unassigned"
          ? "No unassigned tickets are waiting."
          : view === "waiting"
            ? "No tickets are waiting for a customer reply."
            : "Your queue is clear."
      }
      isFetching={isFetching || claimMutation.isPending}
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
