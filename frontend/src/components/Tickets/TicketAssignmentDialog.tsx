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
      showSuccessToast(ticket.assignee ? "Ticket reassigned." : "Ticket assigned.")
    },
    onError: handleError.bind(showErrorToast),
  })

  const unassignMutation = useMutation({
    mutationFn: () =>
      TicketsService.unassignTicket({ path: { ticket_id: ticket.id } }),
    onSuccess: async () => {
      await refresh()
      setOpen(false)
      showSuccessToast("Ticket returned to the unassigned queue.")
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
          {hasAssignee ? "Change assignee" : "Assign ticket"}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{hasAssignee ? "Change assignee" : "Assign ticket"}</DialogTitle>
          <DialogDescription>
            Only active Agent accounts can receive this ticket.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <label htmlFor="ticket-assignee" className="text-sm font-medium">
            Agent
          </label>
          <Select
            value={selectedAgentId}
            onValueChange={setSelectedAgentId}
            disabled={isPending || agentsQuery.isPending}
          >
            <SelectTrigger id="ticket-assignee">
              <SelectValue
                placeholder={
                  agentsQuery.isPending ? "Loading agents..." : "Select an agent"
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
                Unassign
              </LoadingButton>
            )}
          </div>
          <div className="flex gap-2">
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={isPending}>
                Cancel
              </Button>
            </DialogClose>
            <LoadingButton
              type="button"
              loading={assignMutation.isPending}
              disabled={!canAssign || isPending}
              onClick={() => assignMutation.mutate(selectedAgentId)}
            >
              Save assignment
            </LoadingButton>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
