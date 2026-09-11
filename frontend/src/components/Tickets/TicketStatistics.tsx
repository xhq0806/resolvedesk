import type { LucideIcon } from "lucide-react"
import {
  CheckCircle2,
  CircleDot,
  Clock3,
  Inbox,
  ListChecks,
  TriangleAlert,
  UserRound,
  UsersRound,
} from "lucide-react"

import type {
  TicketStatisticsPublic,
  TicketStatus,
  UserRole,
} from "@/client"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

type StatisticCard = {
  label: string
  value: number
  icon: LucideIcon
  tone: "default" | "warning" | "success"
}

const statusLabels: Record<TicketStatus, string> = {
  OPEN: "待处理",
  IN_PROGRESS: "处理中",
  WAITING_FOR_CUSTOMER: "等待客户",
  RESOLVED: "已解决",
  CLOSED: "已关闭",
}

const statusIcons: Record<TicketStatus, LucideIcon> = {
  OPEN: CircleDot,
  IN_PROGRESS: Clock3,
  WAITING_FOR_CUSTOMER: UsersRound,
  RESOLVED: CheckCircle2,
  CLOSED: CheckCircle2,
}

const roleLabels: Record<UserRole, string> = {
  CUSTOMER: "客户工作台",
  AGENT: "客服工作台",
  ADMIN: "管理员工作台",
}

const toneClasses: Record<StatisticCard["tone"], string> = {
  default: "bg-primary/10 text-primary",
  warning: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
}

const statusTone = (status: TicketStatus): StatisticCard["tone"] => {
  if (status === "WAITING_FOR_CUSTOMER") return "warning"
  if (status === "RESOLVED" || status === "CLOSED") return "success"
  return "default"
}

// 统计卡片只消费后端已经按角色裁剪的结果，避免前端重新推断权限范围。by AI.Coding
export function TicketStatistics({
  statistics,
}: {
  statistics: TicketStatisticsPublic
}) {
  const cards = getStatisticCards(statistics)

  return (
    <section
      aria-label="工单统计"
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
    >
      {cards.map(({ label, value, icon: Icon, tone }) => (
        <Card key={label} className="gap-4 py-5">
          <CardHeader className="flex flex-row items-center justify-between gap-3 px-5">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {label}
            </CardTitle>
            <span className={`rounded-lg p-2 ${toneClasses[tone]}`}>
              <Icon className="h-4 w-4" aria-hidden="true" />
            </span>
          </CardHeader>
          <CardContent className="px-5">
            <p className="text-3xl font-semibold tracking-tight">{value}</p>
          </CardContent>
        </Card>
      ))}
    </section>
  )
}

// 角色对应的卡片顺序保持稳定，确保 Dashboard 在不同角色间仍然容易扫描。by AI.Coding
function getStatisticCards(statistics: TicketStatisticsPublic): StatisticCard[] {
  if (statistics.role === "AGENT") {
    return [
      {
        label: "未分派",
        value: statistics.unassigned_count ?? 0,
        icon: Inbox,
        tone: "warning",
      },
      {
        label: "分派给我",
        value: statistics.assigned_to_me_count ?? 0,
        icon: UserRound,
        tone: "default",
      },
      {
        label: "等待客户",
        value: statistics.waiting_for_customer_count ?? 0,
        icon: UsersRound,
        tone: "warning",
      },
      {
        label: "进行中的工作",
        value: getStatusTotal(statistics, ["OPEN", "IN_PROGRESS"]),
        icon: ListChecks,
        tone: "success",
      },
    ]
  }

  if (statistics.role === "ADMIN") {
    return [
      {
        label: "工单总数",
        value: getStatusTotal(statistics, [
          "OPEN",
          "IN_PROGRESS",
          "WAITING_FOR_CUSTOMER",
          "RESOLVED",
          "CLOSED",
        ]),
        icon: ListChecks,
        tone: "default",
      },
      {
        label: "待处理",
        value: statistics.status_counts?.OPEN ?? 0,
        icon: statusIcons.OPEN,
        tone: "default",
      },
      {
        label: "未分派",
        value: statistics.unassigned_count ?? 0,
        icon: Inbox,
        tone: "warning",
      },
      {
        label: "紧急",
        value: statistics.priority_counts?.URGENT ?? 0,
        icon: TriangleAlert,
        tone: "warning",
      },
    ]
  }

  return (["OPEN", "IN_PROGRESS", "WAITING_FOR_CUSTOMER", "RESOLVED"] as const).map(
    (status) => ({
      label: statusLabels[status],
      value: statistics.status_counts?.[status] ?? 0,
      icon: statusIcons[status],
      tone: statusTone(status),
    }),
  )
}

function getStatusTotal(
  statistics: TicketStatisticsPublic,
  statuses: TicketStatus[],
) {
  return statuses.reduce(
    (total, status) => total + (statistics.status_counts?.[status] ?? 0),
    0,
  )
}

export function TicketStatisticsHeading({
  role,
}: {
  role: UserRole
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        ResolveDesk 工作台
      </p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">
        {roleLabels[role]}
      </h1>
      <p className="mt-1 text-muted-foreground">
        清晰掌握工作进展，持续推进客户请求。
      </p>
    </div>
  )
}
