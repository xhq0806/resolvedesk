import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Settings2 } from "lucide-react"

import type {
  TicketCategory,
  TicketDetailPublic,
  TicketPriority,
  TicketStatus,
  UserRole,
} from "@/client"
import { TicketsService } from "@/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { invalidateTicketQueries } from "@/lib/ticketQueries"
import { handleError } from "@/utils"
import { DeleteTicketDialog } from "./DeleteTicketDialog"
import { TicketAssignmentDialog } from "./TicketAssignmentDialog"

const statusLabels: Record<TicketStatus, string> = {
  OPEN: "待处理",
  IN_PROGRESS: "处理中",
  WAITING_FOR_CUSTOMER: "等待客户",
  RESOLVED: "已解决",
  CLOSED: "已关闭",
}

const priorityLabels: Record<TicketPriority, string> = {
  LOW: "低",
  MEDIUM: "中",
  HIGH: "高",
  URGENT: "紧急",
}

const categoryLabels: Record<TicketCategory, string> = {
  ACCOUNT: "账号问题",
  BILLING: "账单问题",
  PRODUCT: "产品咨询",
  BUG: "缺陷反馈",
  FEATURE_REQUEST: "功能建议",
  OTHER: "其他",
}

const statusTargets: Record<
  Exclude<TicketStatus, "CLOSED">,
  readonly TicketStatus[]
> = {
  OPEN: [],
  IN_PROGRESS: ["WAITING_FOR_CUSTOMER", "RESOLVED"],
  WAITING_FOR_CUSTOMER: ["IN_PROGRESS", "RESOLVED"],
  RESOLVED: ["IN_PROGRESS", "CLOSED"],
}

// 仅展示后端状态机允许的目标，OPEN 仍通过接手或 Admin 分派进入处理中。by AI.Coding
const getAllowedStatusTargets = (
  ticket: TicketDetailPublic,
  role: UserRole,
  currentUserId: string | undefined,
) => {
  if (ticket.status === "CLOSED") return []
  if (
    role === "AGENT" &&
    (!ticket.assignee || ticket.assignee.id !== currentUserId)
  ) {
    return []
  }
  if (role === "CUSTOMER") return []

  return statusTargets[ticket.status as Exclude<TicketStatus, "CLOSED">] ?? []
}

// 统一承载状态、属性、Admin 分派和删除操作，详情页只负责提供角色上下文。by AI.Coding
export function TicketActionPanel({
  ticket,
  role,
  currentUserId,
  onDeleted,
}: {
  ticket: TicketDetailPublic
  role: UserRole
  currentUserId?: string
  onDeleted: () => void
}) {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const isClosed = ticket.status === "CLOSED"
  const canManage =
    !isClosed &&
    (role === "ADMIN" ||
      (role === "AGENT" && ticket.assignee?.id === currentUserId))
  const allowedStatuses = getAllowedStatusTargets(
    ticket,
    role,
    currentUserId,
  )

  const statusMutation = useMutation({
    mutationFn: (status: TicketStatus) =>
      TicketsService.updateStatus({
        path: { ticket_id: ticket.id },
        body: { status },
      }),
    onSuccess: async () => {
      await invalidateTicketQueries(queryClient, { ticketId: ticket.id })
      showSuccessToast("工单状态已更新。")
    },
    onError: handleError.bind(showErrorToast),
  })

  const attributesMutation = useMutation({
    mutationFn: (body: { priority?: TicketPriority; category?: TicketCategory }) =>
      TicketsService.updateAttributes({
        path: { ticket_id: ticket.id },
        body,
      }),
    onSuccess: async () => {
      await invalidateTicketQueries(queryClient, { ticketId: ticket.id })
      showSuccessToast("工单详情已更新。")
    },
    onError: handleError.bind(showErrorToast),
  })

  const isPending = statusMutation.isPending || attributesMutation.isPending

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings2 className="h-4 w-4" />
          工单操作
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        {allowedStatuses.length > 0 && (
          <ActionSelect
            id="ticket-status"
            label="状态"
            value={ticket.status}
            disabled={isPending}
            options={[ticket.status, ...allowedStatuses].filter(
              (value, index, values) => values.indexOf(value) === index,
            )}
            labels={statusLabels}
            onChange={(value) => statusMutation.mutate(value as TicketStatus)}
          />
        )}

        {canManage && (
          <>
            <ActionSelect
              id="ticket-priority"
              label="优先级"
              value={ticket.priority}
              disabled={isPending}
              options={Object.keys(priorityLabels) as TicketPriority[]}
              labels={priorityLabels}
              onChange={(value) =>
                attributesMutation.mutate({ priority: value as TicketPriority })
              }
            />
            <ActionSelect
              id="ticket-category"
              label="分类"
              value={ticket.category}
              disabled={isPending}
              options={Object.keys(categoryLabels) as TicketCategory[]}
              labels={categoryLabels}
              onChange={(value) =>
                attributesMutation.mutate({ category: value as TicketCategory })
              }
            />
          </>
        )}

        {role === "ADMIN" && !isClosed && (
          <TicketAssignmentDialog ticket={ticket} />
        )}

        {role === "ADMIN" && (
          <DeleteTicketDialog ticketId={ticket.id} onDeleted={onDeleted} />
        )}

        {isClosed && (
          <p className="text-sm text-muted-foreground">
            已关闭的工单只能查看，不能编辑。
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function ActionSelect<T extends string>({
  id,
  label,
  value,
  options,
  labels,
  disabled,
  onChange,
}: {
  id: string
  label: string
  value: T
  options: readonly T[]
  labels: Record<T, string>
  disabled: boolean
  onChange: (value: string) => void
}) {
  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </label>
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger id={id}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {labels[option]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
