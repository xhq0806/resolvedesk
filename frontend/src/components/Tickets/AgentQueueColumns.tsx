import type { ColumnDef } from "@tanstack/react-table"
import { Hand, Loader2 } from "lucide-react"

import type { TicketPublic } from "@/client"
import { Button } from "@/components/ui/button"
import { createTicketColumns } from "./TicketColumns"

interface AgentQueueColumnsOptions {
  onClaim: (ticketId: string) => void
  claimingTicketId?: string
}

// 仅为未分派工单提供接手动作，已分派工单不重复显示客服操作。by AI.Coding
export const createAgentQueueColumns = ({
  onClaim,
  claimingTicketId,
}: AgentQueueColumnsOptions): ColumnDef<TicketPublic>[] => [
  ...createTicketColumns("/queue/$ticketId"),
  {
    id: "actions",
    header: "Action",
    cell: ({ row }) => {
      const ticket = row.original
      const isClaiming = claimingTicketId === ticket.id

      if (ticket.assignee) return null

      return (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onClaim(ticket.id)}
          disabled={claimingTicketId !== undefined}
          aria-label={`Claim ${ticket.ticket_number}`}
        >
          {isClaiming ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Hand className="h-4 w-4" />
          )}
          Claim
        </Button>
      )
    },
  },
]
