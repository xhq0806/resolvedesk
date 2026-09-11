import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowRight, Inbox, ListTodo, type LucideIcon, Users } from "lucide-react"
import { type ReactNode, Suspense } from "react"
import { z } from "zod"
import {
  TicketStatistics,
  TicketStatisticsHeading,
} from "@/components/Tickets/TicketStatistics"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import useAuth from "@/hooks/useAuth"
import { getUserRole } from "@/lib/routeGuards"
import { ticketStatisticsQueryOptions } from "@/lib/ticketQueries"

const searchSchema = z.object({
  access: z.enum(["denied"]).optional(),
})

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  validateSearch: searchSchema,
  head: () => ({
    meta: [{ title: "工作台 - ResolveDesk" }],
  }),
})

function Dashboard() {
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <DashboardContent />
    </Suspense>
  )
}

function DashboardContent() {
  const { user: currentUser } = useAuth()
  const { access } = Route.useSearch()
  const role = getUserRole(currentUser)
  const { data: statistics } = useSuspenseQuery(ticketStatisticsQueryOptions())

  return (
    <div className="flex flex-col gap-8">
      {access === "denied" && (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          你没有权限访问该区域。
        </p>
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <TicketStatisticsHeading role={role} />
        <p className="text-sm text-muted-foreground">
          当前登录账号：{currentUser?.full_name || currentUser?.email}
        </p>
      </div>
      <TicketStatistics statistics={statistics} />
      <QuickLinks role={role} />
    </div>
  )
}

// 快捷入口只展示当前角色可访问的页面，避免 Dashboard 产生越权导航。by AI.Coding
function QuickLinks({ role }: { role: ReturnType<typeof getUserRole> }) {
  if (role === "CUSTOMER") {
    return (
      <QuickLinksCard
        title="继续处理你的客服请求"
        description="查看已有工单，或向客服团队发起新的咨询。"
      >
        <Link
          to="/tickets"
          search={{ page: 1, pageSize: 20, query: "" }}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <QuickLinkContent icon={Inbox} label="查看我的工单" />
        </Link>
      </QuickLinksCard>
    )
  }

  if (role === "AGENT") {
    return (
      <QuickLinksCard
        title="让客服队列持续运转"
        description="接手未分派工单、回复客户，并关闭已解决的请求。"
      >
        <Link
          to="/queue"
          search={{ view: "unassigned", page: 1, pageSize: 20, query: "" }}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <QuickLinkContent icon={ListTodo} label="打开客服队列" />
        </Link>
      </QuickLinksCard>
    )
  }

  return (
    <QuickLinksCard
        title="管理工作空间"
        description="查看全局工单队列，或更新用户角色和账号状态。"
    >
      <div className="flex flex-wrap gap-3">
        <Link
          to="/admin/tickets"
          search={{ page: 1, pageSize: 20, query: "" }}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <QuickLinkContent icon={Inbox} label="管理工单" />
        </Link>
        <Link
          to="/admin"
          search={{ page: 1, pageSize: 20, query: "" }}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <QuickLinkContent icon={Users} label="管理用户" />
        </Link>
      </div>
    </QuickLinksCard>
  )
}

function QuickLinksCard({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function QuickLinkContent({
  icon: Icon,
  label,
}: {
  icon: LucideIcon
  label: string
}) {
  return (
    <>
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label}
      <ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
    </>
  )
}

function DashboardSkeleton() {
  return (
    <div
      className="flex flex-col gap-6"
      role="status"
      aria-label="正在加载工作台"
    >
      <div className="h-20 animate-pulse rounded-xl bg-muted" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-32 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    </div>
  )
}
