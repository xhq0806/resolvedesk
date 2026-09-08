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
import { invalidateTicketQueries } from "@/lib/ticketQueries"
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
      await invalidateTicketQueries(queryClient, { ticketId })
      showSuccessToast("Ticket deleted.")
      setOpen(false)
      setConfirmed(false)
      onDeleted()
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
          Delete ticket
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete ticket</DialogTitle>
          <DialogDescription>
            This removes the ticket from business queries and cannot be undone.
            Its audit record is retained.
          </DialogDescription>
        </DialogHeader>
        <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
          <Checkbox
            checked={confirmed}
            onCheckedChange={(value) => setConfirmed(value === true)}
            disabled={mutation.isPending}
          />
          <span>I understand this ticket will no longer be available.</span>
        </label>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            type="button"
            variant="destructive"
            loading={mutation.isPending}
            disabled={!confirmed}
            onClick={() => mutation.mutate()}
          >
            Delete ticket
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
