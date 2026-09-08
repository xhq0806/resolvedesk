import type { QueryClient } from "@tanstack/react-query"
import { z } from "zod"

import type { UserRole, UsersPublic } from "@/client"
import { UsersService } from "@/client"
import { userKeys } from "@/hooks/useAuth"
import { agentKeys } from "@/lib/ticketQueries"

export type UserListFilters = {
  page: number
  pageSize: number
  query: string
  role: UserRole | null
  isActive: boolean | null
}

export type UserFilterChange = Partial<UserListFilters>

export const DEFAULT_USER_LIST_FILTERS: UserListFilters = {
  page: 1,
  pageSize: 25,
  query: "",
  role: null,
  isActive: null,
}

const userRoleValues = ["CUSTOMER", "AGENT", "ADMIN"] as const

// URL 查询参数里的布尔值可能来自字符串或数字，这里统一收敛成稳定的 boolean。by AI.Coding
const parseSearchBoolean = (value: unknown) => {
  if (value === undefined || value === null || value === "") {
    return undefined
  }

  if (typeof value === "boolean") {
    return value
  }

  if (typeof value === "number") {
    return value !== 0
  }

  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase()
    if (normalized === "true") return true
    if (normalized === "false") return false
  }

  return value
}

export const userSearchSchema = z.object({
  page: z.coerce.number().int().min(1).catch(1),
  pageSize: z.coerce.number().int().min(1).max(100).catch(25),
  query: z.string().trim().catch(""),
  role: z.enum(userRoleValues).optional(),
  isActive: z.preprocess(parseSearchBoolean, z.boolean().optional()),
})

export type UserSearch = z.infer<typeof userSearchSchema>

// 管理端列表使用规范化 URL 参数，避免等价筛选产生不同 Query key。by AI.Coding
export const normalizeUserListFilters = (
  filters: Partial<UserListFilters> = {},
): UserListFilters => ({
  page: Math.max(1, Math.floor(filters.page ?? DEFAULT_USER_LIST_FILTERS.page)),
  pageSize: Math.min(
    100,
    Math.max(
      1,
      Math.floor(filters.pageSize ?? DEFAULT_USER_LIST_FILTERS.pageSize),
    ),
  ),
  query: filters.query?.trim() ?? DEFAULT_USER_LIST_FILTERS.query,
  role: filters.role ?? DEFAULT_USER_LIST_FILTERS.role,
  isActive: filters.isActive ?? DEFAULT_USER_LIST_FILTERS.isActive,
})

// 路由 search 先转成列表过滤器，再进入查询键和 API 载荷，避免分散归一化逻辑。by AI.Coding
export const userSearchToFilters = (
  search: UserSearch,
): UserListFilters => normalizeUserListFilters(search)

export const userFiltersToSearch = (filters: UserListFilters): UserSearch => {
  const normalized = normalizeUserListFilters(filters)

  return {
    page: normalized.page,
    pageSize: normalized.pageSize,
    query: normalized.query,
    role: normalized.role ?? undefined,
    isActive: normalized.isActive ?? undefined,
  }
}

export const userListKeys = {
  all: ["users", "list"] as const,
  list: (filters: UserListFilters) => {
    const normalized = normalizeUserListFilters(filters)

    return [
      ...userListKeys.all,
      {
        page: normalized.page,
        pageSize: normalized.pageSize,
        query: normalized.query,
        role: normalized.role,
        isActive: normalized.isActive,
      },
    ] as const
  },
}

export const userListQueryOptions = (
  filters: Partial<UserListFilters> = {},
) => {
  const normalized = normalizeUserListFilters(filters)

  return {
    queryKey: userListKeys.list(normalized),
    queryFn: async (): Promise<UsersPublic> => {
      const response = await UsersService.readUsers({
        query: {
          page: normalized.page,
          page_size: normalized.pageSize,
          query: normalized.query || undefined,
          role: normalized.role,
          is_active: normalized.isActive,
        },
      })

      if (!response.data) {
        throw new Error("User list response is empty")
      }

      return response.data
    },
  }
}

// 用户角色或启停变化会影响管理表、分派候选和可能的当前会话。by AI.Coding
export const invalidateUserQueries = async (
  queryClient: QueryClient,
  options: { includeCurrentUser?: boolean } = {},
) => {
  const invalidations = [
    queryClient.invalidateQueries({ queryKey: userListKeys.all }),
    queryClient.invalidateQueries({ queryKey: agentKeys }),
  ]

  if (options.includeCurrentUser) {
    invalidations.push(
      queryClient.invalidateQueries({ queryKey: userKeys.current }),
    )
  }

  await Promise.all(invalidations)
}
