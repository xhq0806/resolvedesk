import type {
  TicketAuditAction,
  TicketAuditPublic,
  TicketMessagePublic,
} from "@/client"
import { Badge } from "@/components/ui/badge"
import { getInitials } from "@/utils"

type TimelineEntry =
  | { kind: "message"; value: TicketMessagePublic }
  | { kind: "audit"; value: TicketAuditPublic }

const auditLabels: Record<TicketAuditAction, string> = {
  TAKEN: "Ticket claimed",
  ASSIGNED: "Ticket assigned",
  REASSIGNED: "Ticket reassigned",
  UNASSIGNED: "Assignment removed",
  STATUS_CHANGED: "Status changed",
  PRIORITY_CHANGED: "Priority changed",
  CATEGORY_CHANGED: "Category changed",
  DELETED: "Ticket deleted",
}

const formatDate = (value: string) =>
  new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))

const displayName = (author: TicketMessagePublic["author"]) =>
  author.full_name?.trim() || author.email

const formatSnapshot = (value: Record<string, unknown> | null | undefined) => {
  if (!value) return ""

  return Object.entries(value)
    .map(([key, entry]) => `${key.replace(/_/g, " ")}: ${String(entry)}`)
    .join(" · ")
}

// 展示后端按角色裁剪后的消息和审计事件，不在前端自行判断内部备注权限。by AI.Coding
export function TicketTimeline({
  messages,
  auditLogs,
}: {
  messages: TicketMessagePublic[]
  auditLogs: TicketAuditPublic[]
}) {
  const entries: TimelineEntry[] = [
    ...messages.map((value) => ({ kind: "message" as const, value })),
    ...auditLogs.map((value) => ({ kind: "audit" as const, value })),
  ].sort((left, right) => {
    const timeDifference =
      new Date(left.value.created_at).getTime() -
      new Date(right.value.created_at).getTime()

    if (timeDifference !== 0) return timeDifference
    return left.value.id.localeCompare(right.value.id)
  })

  if (entries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed px-6 py-10 text-center text-sm text-muted-foreground">
        No updates have been posted yet.
      </div>
    )
  }

  return (
    <div className="relative grid gap-4 before:absolute before:bottom-5 before:left-4 before:top-5 before:w-px before:bg-border">
      {entries.map((entry) => {
        if (entry.kind === "audit") {
          const audit = entry.value
          const snapshot = formatSnapshot(audit.new_value)

          return (
            <div key={`audit-${audit.id}`} className="relative flex gap-3">
              <div className="z-[1] flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-background text-xs font-semibold text-muted-foreground">
                ·
              </div>
              <div className="min-w-0 flex-1 rounded-lg border bg-muted/30 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">{auditLabels[audit.action]}</p>
                  <time className="text-xs text-muted-foreground">
                    {formatDate(audit.created_at)}
                  </time>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {displayName(audit.actor)}
                  {snapshot ? ` · ${snapshot}` : ""}
                </p>
              </div>
            </div>
          )
        }

        const message = entry.value
        const isInternal = message.message_type === "INTERNAL_NOTE"

        return (
          <div key={`message-${message.id}`} className="relative flex gap-3">
            <div
              className={`z-[1] flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                isInternal
                  ? "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200"
                  : "bg-primary text-primary-foreground"
              }`}
            >
              {getInitials(displayName(message.author)) || "?"}
            </div>
            <div
              className={`min-w-0 flex-1 rounded-lg border px-4 py-3 ${
                isInternal
                  ? "border-amber-300/70 bg-amber-50/70 dark:border-amber-900 dark:bg-amber-950/30"
                  : "bg-card"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium">{displayName(message.author)}</p>
                  <Badge variant={isInternal ? "outline" : "secondary"}>
                    {isInternal ? "Internal note" : "Public reply"}
                  </Badge>
                </div>
                <time className="text-xs text-muted-foreground">
                  {formatDate(message.created_at)}
                </time>
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-foreground">
                {message.content}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
