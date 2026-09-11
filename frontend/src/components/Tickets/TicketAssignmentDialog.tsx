import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { UserRoundCog } from "lucide-react"
import { useEffect, useState } from "react"

import type { TicketDetailPublic } from "@/client"
import { TicketsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import {
  activeAgentsQueryOptions,
  invalidateTicketQueries,
} from "@/lib/ticketQueries"
import { handleError } from "@/utils"

// Admin 使用同一对话框完成首次分派、转派和取消分派，后端负责最终权限校验。by AI.Coding
export function TicketAssignmentDialog({
  ticket,
}: {
  ticket: TicketDetailPublic
}) {
  const [open, setOpen] = useState(false)
  const [selectedAgentId, setSelectedAgentId] = useState("")
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const agentsQuery = useQuery({
    ...activeAgentsQueryOptions(),
    enabled: open,
  })

  useEffect(() => {
    if (open) setSelectedAgentId(ticket.assignee?.id ?? "")
  }, [open, ticket.assignee?.id])

  const refresh = async () =>
    invalidateTicketQueries(queryClient, {
      ticketId: ticket.id,
      includeAgents: true,
    })

  const assignMutation = useMutation({
    mutationFn: (assigneeId: string) =>
      TicketsService.assignTicket({
        path: { ticket_id: ticket.id },
        body: { assignee_id: assigneeId },
      }),
    onSuccess: async () => {
      await refresh()
      setOpen(false)
      showSuccessToast(ticket.assignee ? "工单已转派。" : "工单已分派。")
    },
    onError: handleError.bind(showErrorToast),
  })

  const unassignMutation = useMutation({
    mutationFn: () =>
      TicketsService.unassignTicket({ path: { ticket_id: ticket.id } }),
    onSuccess: async () => {
      await refresh()
      setOpen(false)
      showSuccessToast("工单已返回未分派队列。")
    },
    onError: handleError.bind(showErrorToast),
  })

  const isPending = assignMutation.isPending || unassignMutation.isPending
  const hasAssignee = Boolean(ticket.assignee)
  const canAssign = selectedAgentId.length > 0

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!isPending) setOpen(nextOpen)
      }}
    >
      <DialogTrigger asChild>
        <Button type="button" variant="outline" className="w-full">
          <UserRoundCog className="h-4 w-4" />
          {hasAssignee ? "更换负责人" : "分派工单"}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{hasAssignee ? "更换负责人" : "分派工单"}</DialogTitle>
          <DialogDescription>
            只有已启用的客服账号可以接收工单。
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <label htmlFor="ticket-assignee" className="text-sm font-medium">
            客服
          </label>
          <Select
            value={selectedAgentId}
            onValueChange={setSelectedAgentId}
            disabled={isPending || agentsQuery.isPending}
          >
            <SelectTrigger id="ticket-assignee">
              <SelectValue
                placeholder={
                  agentsQuery.isPending ? "正在加载客服……" : "请选择客服"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {agentsQuery.data?.map((agent) => (
                <SelectItem key={agent.id} value={agent.id}>
                  {agent.full_name?.trim() || agent.email}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <DialogFooter className="gap-2 sm:justify-between">
          <div>
            {hasAssignee && (
              <LoadingButton
                type="button"
                variant="outline"
                loading={unassignMutation.isPending}
                disabled={isPending}
                onClick={() => unassignMutation.mutate()}
              >
                取消分派
              </LoadingButton>
            )}
          </div>
          <div className="flex gap-2">
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={isPending}>
                取消
              </Button>
            </DialogClose>
            <LoadingButton
              type="button"
              loading={assignMutation.isPending}
              disabled={!canAssign || isPending}
              onClick={() => assignMutation.mutate(selectedAgentId)}
            >
              保存分派
            </LoadingButton>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
