import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { UserFilters } from "@/components/Admin/UserFilters"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import useAuth from "@/hooks/useAuth"
import {
  normalizeUserListFilters,
  type UserFilterChange,
  userFiltersToSearch,
  userListQueryOptions,
  userSearchSchema,
  userSearchToFilters,
} from "@/lib/userQueries"

// Admin 用户页直接跟随 URL 搜索参数和服务端分页，保持刷新和前进后退一致。by AI.Coding
export const Route = createFileRoute("/_layout/admin/")({
  component: AdminUsers,
  validateSearch: userSearchSchema,
  head: () => ({
    meta: [{ title: "Users - ResolveDesk" }],
  }),
})

function UsersTableContent() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { user: currentUser } = useAuth()
  // 路由 search 负责唯一来源的筛选状态，查询和表格分页都从这里派生。by AI.Coding
  const filters = userSearchToFilters(search)
  const { data: users, isFetching } = useSuspenseQuery(
    userListQueryOptions(filters),
  )

  const updateFilters = (change: UserFilterChange) => {
    // 任何筛选变化都重置分页，避免停留在无效页码。by AI.Coding
    const nextFilters = normalizeUserListFilters({ ...filters, ...change })
    void navigate({ search: userFiltersToSearch(nextFilters) })
  }

  const tableData: UserTableData[] = users.data.map((user) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return (
    <DataTable
      columns={columns}
      data={tableData}
      // 用户管理使用受控服务端分页，保持总数和页码稳定。by AI.Coding
      toolbar={
        <UserFilters filters={filters} onChange={updateFilters} />
      }
      emptyState="No users match the current filters."
      isFetching={isFetching}
      pagination={{
        pageIndex: filters.page - 1,
        pageSize: filters.pageSize,
        totalCount: users.count,
        onPageChange: (pageIndex) => updateFilters({ page: pageIndex + 1 }),
        onPageSizeChange: (pageSize) => updateFilters({ page: 1, pageSize }),
      }}
    />
  )
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function AdminUsers() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Users</h1>
          <p className="text-muted-foreground">
            Manage user accounts and permissions
          </p>
        </div>
        <AddUser />
      </div>
      <UsersTable />
    </div>
  )
}
