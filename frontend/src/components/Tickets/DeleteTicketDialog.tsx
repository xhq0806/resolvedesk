import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { TicketsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import useCustomToast from "@/hooks/useCustomToast"
import { invalidateTicketQueries, ticketKeys } from "@/lib/ticketQueries"
import { handleError } from "@/utils"

// Admin 删除入口必须经过可见确认，并把 confirm=true 传给后端契约。by AI.Coding
export function DeleteTicketDialog({
  ticketId,
  onDeleted,
}: {
  ticketId: string
  onDeleted: () => void
}) {
  const [open, setOpen] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () =>
      TicketsService.deleteTicket({
        path: { ticket_id: ticketId },
        body: { confirm: true },
      }),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: ticketKeys.detail(ticketId) })
      showSuccessToast("工单已删除。")
      setOpen(false)
      setConfirmed(false)
      onDeleted()
      await invalidateTicketQueries(queryClient)
    },
    onError: handleError.bind(showErrorToast),
  })

  const handleOpenChange = (nextOpen: boolean) => {
    if (!mutation.isPending) {
      setOpen(nextOpen)
      if (!nextOpen) setConfirmed(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="destructive" className="w-full">
          <Trash2 className="h-4 w-4" />
          删除工单
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>删除工单</DialogTitle>
          <DialogDescription>
            工单将从业务查询中移除，且无法撤销；系统仍会保留其审计记录。
          </DialogDescription>
        </DialogHeader>
        <label
          htmlFor="confirm-ticket-deletion"
          className="flex items-start gap-3 rounded-md border p-3 text-sm"
        >
          <Checkbox
            id="confirm-ticket-deletion"
            checked={confirmed}
            onCheckedChange={(value) => setConfirmed(value === true)}
            disabled={mutation.isPending}
          />
          <span>我了解该工单删除后将不再可用。</span>
        </label>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={mutation.isPending}>
              取消
            </Button>
          </DialogClose>
          <LoadingButton
            type="button"
            variant="destructive"
            loading={mutation.isPending}
            disabled={!confirmed}
            onClick={() => mutation.mutate()}
          >
            删除工单
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
