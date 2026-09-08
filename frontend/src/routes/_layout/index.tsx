import { useSuspenseQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { ArrowRight, Inbox, ListTodo, Users, type LucideIcon } from "lucide-react"
import { Suspense, type ReactNode } from "react"
import { z } from "zod"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  TicketStatistics,
  TicketStatisticsHeading,
} from "@/components/Tickets/TicketStatistics"
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
    meta: [{ title: "Dashboard - ResolveDesk" }],
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
          You do not have permission to access that area.
        </p>
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <TicketStatisticsHeading role={role} />
        <p className="text-sm text-muted-foreground">
          Signed in as {currentUser?.full_name || currentUser?.email}
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
        title="Continue with your support requests"
        description="Review existing tickets or start a new conversation with the support team."
      >
        <Link
          to="/tickets"
          search={{ page: 1, pageSize: 25, query: "" }}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <QuickLinkContent icon={Inbox} label="Open my tickets" />
        </Link>
      </QuickLinksCard>
    )
  }

  if (role === "AGENT") {
    return (
      <QuickLinksCard
        title="Keep the queue moving"
        description="Claim unassigned work, respond to customers, and close resolved requests."
      >
        <Link
          to="/queue"
          search={{ view: "unassigned", page: 1, pageSize: 25, query: "" }}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <QuickLinkContent icon={ListTodo} label="Open service queue" />
        </Link>
      </QuickLinksCard>
    )
  }

  return (
    <QuickLinksCard
      title="Manage the workspace"
      description="Review the global ticket queue or update roles and account status."
    >
      <div className="flex flex-wrap gap-3">
        <Link
          to="/admin/tickets"
          search={{ page: 1, pageSize: 25, query: "" }}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <QuickLinkContent icon={Inbox} label="Manage tickets" />
        </Link>
        <Link
          to="/admin"
          search={{ page: 1, pageSize: 25, query: "" }}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          <QuickLinkContent icon={Users} label="Manage users" />
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
      aria-label="Loading dashboard"
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
