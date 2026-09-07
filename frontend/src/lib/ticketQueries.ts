import type { QueryClient } from "@tanstack/react-query"
import { z } from "zod"

import type {
  TicketCategory,
  TicketPriority,
  TicketStatus,
  TicketStatisticsPublic,
  TicketsPublic,
} from "@/client"
import { TicketsService } from "@/client"

export type TicketScope = "customer" | "agent-queue" | "agent-mine" | "admin"

export type TicketListFilters = {
  page: number
  pageSize: number
  query: string
  status: TicketStatus | null
  priority: TicketPriority | null
  category: TicketCategory | null
  assigneeId: string | null
}

export type TicketFilterChange = Partial<
  Pick<
    TicketListFilters,
    "pageSize" | "query" | "status" | "priority" | "category" | "assigneeId"
  >
> & {
  page?: number
}

export const DEFAULT_TICKET_LIST_FILTERS: TicketListFilters = {
  page: 1,
  pageSize: 25,
  query: "",
  status: null,
  priority: null,
  category: null,
  assigneeId: null,
}

const ticketStatusValues = [
  "OPEN",
  "IN_PROGRESS",
  "WAITING_FOR_CUSTOMER",
  "RESOLVED",
  "CLOSED",
] as const

const ticketPriorityValues = ["LOW", "MEDIUM", "HIGH", "URGENT"] as const

const ticketCategoryValues = [
  "ACCOUNT",
  "BILLING",
  "PRODUCT",
  "BUG",
  "FEATURE_REQUEST",
  "OTHER",
] as const

export const ticketSearchSchema = z.object({
  page: z.coerce.number().int().min(1).catch(1),
  pageSize: z.coerce.number().int().min(1).max(100).catch(25),
  query: z.string().trim().catch(""),
  status: z.enum(ticketStatusValues).optional(),
  priority: z.enum(ticketPriorityValues).optional(),
  category: z.enum(ticketCategoryValues).optional(),
  assigneeId: z.string().trim().min(1).optional(),
})

export type TicketSearch = z.infer<typeof ticketSearchSchema>

export const normalizeTicketListFilters = (
  filters: Partial<TicketListFilters> = {},
): TicketListFilters => ({
  page: Math.max(
    1,
    Math.floor(filters.page ?? DEFAULT_TICKET_LIST_FILTERS.page),
  ),
  pageSize: Math.min(
    100,
    Math.max(
      1,
      Math.floor(filters.pageSize ?? DEFAULT_TICKET_LIST_FILTERS.pageSize),
    ),
  ),
  query: filters.query?.trim() ?? DEFAULT_TICKET_LIST_FILTERS.query,
  status: filters.status ?? DEFAULT_TICKET_LIST_FILTERS.status,
  priority: filters.priority ?? DEFAULT_TICKET_LIST_FILTERS.priority,
  category: filters.category ?? DEFAULT_TICKET_LIST_FILTERS.category,
  assigneeId:
    filters.assigneeId?.trim() || DEFAULT_TICKET_LIST_FILTERS.assigneeId,
})

export const ticketSearchToFilters = (
  search: TicketSearch,
): TicketListFilters => normalizeTicketListFilters(search)

export const ticketFiltersToSearch = (
  filters: TicketListFilters,
): TicketSearch => {
  const normalized = normalizeTicketListFilters(filters)

  return {
    page: normalized.page,
    pageSize: normalized.pageSize,
    query: normalized.query,
    status: normalized.status ?? undefined,
    priority: normalized.priority ?? undefined,
    category: normalized.category ?? undefined,
    assigneeId: normalized.assigneeId ?? undefined,
  }
}

export const ticketKeys = {
  all: ["tickets"] as const,
  lists: () => [...ticketKeys.all, "list"] as const,
  list: (scope: TicketScope, filters: TicketListFilters) => {
    const normalized = normalizeTicketListFilters(filters)

    return [
      ...ticketKeys.lists(),
      scope,
      {
        page: normalized.page,
        pageSize: normalized.pageSize,
        query: normalized.query,
        status: normalized.status,
        priority: normalized.priority,
        category: normalized.category,
        assigneeId: normalized.assigneeId,
      },
    ] as const
  },
  details: () => [...ticketKeys.all, "detail"] as const,
  detail: (ticketId: string) => [...ticketKeys.details(), ticketId] as const,
  statistics: () => [...ticketKeys.all, "statistics"] as const,
}

export const agentKeys = ["users", "agents"] as const

export const ticketListQueryOptions = (
  scope: TicketScope,
  filters: Partial<TicketListFilters> = {},
) => {
  const normalized = normalizeTicketListFilters(filters)

  return {
    queryKey: ticketKeys.list(scope, normalized),
    queryFn: async (): Promise<TicketsPublic> => {
      const response = await TicketsService.listTickets({
        query: {
          page: normalized.page,
          page_size: normalized.pageSize,
          query: normalized.query || undefined,
          status: normalized.status,
          priority: normalized.priority,
          category: normalized.category,
          assignee_id: normalized.assigneeId,
        },
      })

      if (!response.data) {
        throw new Error("Ticket list response is empty")
      }

      return response.data
    },
  }
}

// 统计查询与列表使用同一组稳定键，接手后可由统一失效函数刷新。by AI.Coding
export const ticketStatisticsQueryOptions = () => ({
  queryKey: ticketKeys.statistics(),
  queryFn: async (): Promise<TicketStatisticsPublic> => {
    const response = await TicketsService.readTicketStatistics()

    if (!response.data) {
      throw new Error("Ticket statistics response is empty")
    }

    return response.data
  },
})

export const invalidateTicketLists = (queryClient: QueryClient) =>
  queryClient.invalidateQueries({ queryKey: ticketKeys.lists() })

export const invalidateTicketStatistics = (queryClient: QueryClient) =>
  queryClient.invalidateQueries({ queryKey: ticketKeys.statistics() })

export const invalidateTicketDetail = (
  queryClient: QueryClient,
  ticketId: string,
) => queryClient.invalidateQueries({ queryKey: ticketKeys.detail(ticketId) })

// 工单写操作统一失效列表、详情和统计，避免筛选页保留过期状态。by AI.Coding
export const invalidateTicketQueries = async (
  queryClient: QueryClient,
  options: { ticketId?: string; includeAgents?: boolean } = {},
) => {
  const invalidations = [
    invalidateTicketLists(queryClient),
    invalidateTicketStatistics(queryClient),
  ]

  if (options.ticketId) {
    invalidations.push(invalidateTicketDetail(queryClient, options.ticketId))
  }

  if (options.includeAgents) {
    invalidations.push(queryClient.invalidateQueries({ queryKey: agentKeys }))
  }

  await Promise.all(invalidations)
}
