import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query"
import { Link, useNavigate } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import { ArrowLeft, Hand, LockKeyhole } from "lucide-react"

import type { TicketDetailPublic, TicketStatus, UserRole } from "@/client"
import { TicketsService } from "@/client"
import PendingTickets from "@/components/Pending/PendingTickets"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { getUserRole } from "@/lib/routeGuards"
import {
  invalidateTicketQueries,
  ticketDetailQueryOptions,
} from "@/lib/ticketQueries"
import { handleError } from "@/utils"
import { TicketActionPanel } from "./TicketActionPanel"
import { TicketReplyForm } from "./TicketReplyForm"
import { TicketTimeline } from "./TicketTimeline"

type DetailView = "customer" | "agent" | "admin"

const statusLabels: Record<TicketStatus, string> = {
  OPEN: "待处理",
  IN_PROGRESS: "处理中",
  WAITING_FOR_CUSTOMER: "等待客户",
  RESOLVED: "已解决",
  CLOSED: "已关闭",
}

const statusVariants: Record<
  TicketStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  OPEN: "secondary",
  IN_PROGRESS: "default",
  WAITING_FOR_CUSTOMER: "outline",
  RESOLVED: "secondary",
  CLOSED: "outline",
}

const priorityLabels = {
  LOW: "低",
  MEDIUM: "中",
  HIGH: "高",
  URGENT: "紧急",
} as const

const categoryLabels = {
  ACCOUNT: "账号问题",
  BILLING: "账单问题",
  PRODUCT: "产品咨询",
  BUG: "缺陷反馈",
  FEATURE_REQUEST: "功能建议",
  OTHER: "其他",
} as const

const formatDate = (value: string) =>
  new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))

const personName = (person: TicketDetailPublic["requester"]) =>
  person.full_name?.trim() || person.email

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

// 共享三种角色的详情布局，路由只负责传入数据权限和返回入口。by AI.Coding
export function TicketDetailPage({
  ticketId,
  view,
}: {
  ticketId: string
  view: DetailView
}) {
  const { user: currentUser } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const { data: ticket, isFetching } = useSuspenseQuery(
    ticketDetailQueryOptions(ticketId),
  )
  const role = getUserRole(currentUser)
  const isClosed = ticket.status === "CLOSED"
  const isAssignedToCurrentAgent =
    role === "AGENT" && ticket.assignee?.id === currentUser?.id
  const canViewActions = role === "ADMIN" || isAssignedToCurrentAgent
  const canCompose =
    !isClosed &&
    (role === "CUSTOMER" || role === "ADMIN" || isAssignedToCurrentAgent)
  const allowInternal =
    canCompose && (role === "ADMIN" || isAssignedToCurrentAgent)
  const canClaim =
    (view === "agent" || view === "admin") && !ticket.assignee && !isClosed

  const claimMutation = useMutation({
    mutationFn: () =>
      TicketsService.claimTicket({ path: { ticket_id: ticketId } }),
    onSuccess: async () => {
      await invalidateTicketQueries(queryClient, { ticketId })
      showSuccessToast("工单已接手，并已加入你的工作队列。")
    },
    onError: async (error: Error) => {
      if (isClaimConflict(error)) {
        await invalidateTicketQueries(queryClient, { ticketId })
        showErrorToast("其他客服已接手该工单，详情已刷新。")
        return
      }

      handleError.call(showErrorToast, error)
    },
  })

  const backLink =
    view === "customer"
      ? { to: "/tickets" as const, search: { page: 1, pageSize: 20, query: "" } }
      : view === "agent"
        ? {
            to: "/queue" as const,
            search: {
              view: "unassigned" as const,
              page: 1,
              pageSize: 20,
              query: "",
            },
          }
        : { to: "/admin" as const, search: { page: 1, pageSize: 20, query: "" } }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b pb-6">
        <div className="flex min-w-0 items-start gap-3">
          <Button asChild variant="ghost" size="icon" aria-label="返回">
            <Link {...backLink}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div className="min-w-0">
            <p className="font-mono text-xs text-muted-foreground">
              {ticket.ticket_number}
            </p>
            <h1 className="mt-1 break-words text-2xl font-semibold tracking-tight">
              {ticket.title}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              更新时间：{formatDate(ticket.updated_at)}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 pl-12 sm:pl-0">
          <Badge variant={statusVariants[ticket.status]}>
            {statusLabels[ticket.status]}
          </Badge>
          <Badge variant={ticket.priority === "URGENT" ? "destructive" : "outline"}>
            {priorityLabels[ticket.priority]}
          </Badge>
          {canClaim && (
            <Button
              type="button"
              onClick={() => claimMutation.mutate()}
              disabled={claimMutation.isPending || isFetching}
            >
              <Hand className="h-4 w-4" />
              接手工单
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="grid min-w-0 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>工单描述</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
                {ticket.description}
              </p>
            </CardContent>
          </Card>

          <section className="grid gap-4" aria-labelledby="timeline-heading">
            <div>
              <h2 id="timeline-heading" className="text-lg font-semibold">
                沟通时间线
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                当前角色可见的进展和回复。
              </p>
            </div>
            <TicketTimeline
              messages={ticket.messages}
              auditLogs={ticket.audit_logs}
            />
          </section>

          {isClosed ? (
            <div className="flex items-start gap-3 rounded-lg border border-dashed px-4 py-3 text-sm text-muted-foreground">
              <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0" />
              <p>该工单已关闭，只能查看。</p>
            </div>
          ) : (
            canCompose && (
              <TicketReplyForm
                ticketId={ticketId}
                role={role as UserRole}
                allowInternal={allowInternal}
              />
            )
          )}
        </div>

        <aside className="grid h-fit gap-6">
          <Card>
            <CardHeader>
              <CardTitle>工单详情</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 text-sm">
              <DetailField
                label="分类"
                value={categoryLabels[ticket.category]}
              />
              <DetailField
                label="提单人"
                value={personName(ticket.requester)}
              />
              <DetailField
                label="负责人"
                value={
                  ticket.assignee
                    ? `${personName(ticket.assignee)}${ticket.assignee.is_active ? "" : "（已停用）"}`
                    : "未分派"
                }
              />
              <DetailField label="创建时间" value={formatDate(ticket.created_at)} />
            </CardContent>
          </Card>
          {canViewActions && (
            <TicketActionPanel
              ticket={ticket}
              role={role as UserRole}
              currentUserId={currentUser?.id}
              onDeleted={() => {
                // 删除或归档后统一回到 Admin 列表默认页，保持路由状态稳定。by AI.Coding
                void navigate({
                  to: "/admin",
                  search: { page: 1, pageSize: 20, query: "" },
                })
              }}
            />
          )}
        </aside>
      </div>
    </div>
  )
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="break-words text-foreground">{value}</dd>
    </div>
  )
}

export function PendingTicketDetail() {
  return <PendingTickets />
}
