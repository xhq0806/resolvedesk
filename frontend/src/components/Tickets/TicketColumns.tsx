import { Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"

import type { TicketPublic } from "@/client"
import { Badge } from "@/components/ui/badge"

const statusLabels: Record<TicketPublic["status"], string> = {
  OPEN: "待处理",
  IN_PROGRESS: "处理中",
  WAITING_FOR_CUSTOMER: "等待客户",
  RESOLVED: "已解决",
  CLOSED: "已关闭",
}

const priorityLabels: Record<TicketPublic["priority"], string> = {
  LOW: "低",
  MEDIUM: "中",
  HIGH: "高",
  URGENT: "紧急",
}

const categoryLabels: Record<TicketPublic["category"], string> = {
  ACCOUNT: "账号问题",
  BILLING: "账单问题",
  PRODUCT: "产品咨询",
  BUG: "缺陷反馈",
  FEATURE_REQUEST: "功能建议",
  OTHER: "其他",
}

const statusVariants: Record<
  TicketPublic["status"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  OPEN: "secondary",
  IN_PROGRESS: "default",
  WAITING_FOR_CUSTOMER: "outline",
  RESOLVED: "secondary",
  CLOSED: "outline",
}

const priorityVariants: Record<
  TicketPublic["priority"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  LOW: "outline",
  MEDIUM: "secondary",
  HIGH: "default",
  URGENT: "destructive",
}

const formatDate = (value: string) =>
  new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))

type TicketDetailRoute =
  | "/tickets/$ticketId"
  | "/queue/$ticketId"
  | "/admin/tickets/$ticketId"

// 按工作台生成工单列，确保 Customer 和 Agent 点击后进入各自的受保护详情路由。by AI.Coding
export const createTicketColumns = (
  detailRoute: TicketDetailRoute = "/tickets/$ticketId",
): ColumnDef<TicketPublic>[] => [
  {
    accessorKey: "ticket_number",
    header: "工单",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">
        {row.original.ticket_number}
      </span>
    ),
  },
  {
    accessorKey: "title",
    header: "标题",
    cell: ({ row }) => {
      const title = row.original.title
      const description = row.original.description
      const linkClass =
        "block truncate font-medium text-foreground hover:underline"

      // Admin 详情路由没有 search schema，因此单独渲染无查询参数的链接。by AI.Coding
      const link =
        detailRoute === "/admin/tickets/$ticketId" ? (
          <Link
            to={detailRoute}
            params={{ ticketId: row.original.id }}
            search={{ page: 1, pageSize: 20, query: "" }}
            className={linkClass}
          >
            {title}
          </Link>
        ) : detailRoute === "/queue/$ticketId" ? (
          <Link
            to={detailRoute}
            params={{ ticketId: row.original.id }}
            search={{ view: "unassigned", page: 1, pageSize: 20, query: "" }}
            className={linkClass}
          >
            {title}
          </Link>
        ) : (
          <Link
            to={detailRoute}
            params={{ ticketId: row.original.id }}
            search={{ page: 1, pageSize: 20, query: "" }}
            className={linkClass}
          >
            {title}
          </Link>
        )

      return (
        <div className="min-w-48 max-w-md">
          {link}
          <p className="truncate text-xs text-muted-foreground">
            {description}
          </p>
        </div>
      )
    },
  },
  {
    accessorKey: "status",
    header: "状态",
    cell: ({ row }) => (
      <Badge variant={statusVariants[row.original.status]}>
        {statusLabels[row.original.status]}
      </Badge>
    ),
  },
  {
    accessorKey: "priority",
    header: "优先级",
    cell: ({ row }) => (
      <Badge variant={priorityVariants[row.original.priority]}>
        {priorityLabels[row.original.priority]}
      </Badge>
    ),
  },
  {
    accessorKey: "category",
    header: "分类",
    cell: ({ row }) => categoryLabels[row.original.category],
  },
  {
    accessorKey: "assignee",
    header: "负责人",
    cell: ({ row }) => {
      const assignee = row.original.assignee
      return assignee ? (
        <div className="max-w-40 truncate">
          <p className="truncate text-sm">
            {assignee.full_name?.trim() || assignee.email}
          </p>
          <p className="truncate text-xs text-muted-foreground">
            {assignee.email}
          </p>
          {!assignee.is_active && (
            <Badge variant="outline" className="mt-1">
              已停用
            </Badge>
          )}
        </div>
      ) : (
        <span className="text-muted-foreground">未分派</span>
      )
    },
  },
  {
    accessorKey: "updated_at",
    header: "更新时间",
    cell: ({ row }) => (
      <span className="whitespace-nowrap text-sm text-muted-foreground">
        {formatDate(row.original.updated_at)}
      </span>
    ),
  },
]

export const ticketColumns = createTicketColumns()
