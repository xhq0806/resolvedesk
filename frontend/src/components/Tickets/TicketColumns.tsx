import type { ColumnDef } from "@tanstack/react-table"

import type { TicketPublic } from "@/client"
import { Badge } from "@/components/ui/badge"

const statusLabels: Record<TicketPublic["status"], string> = {
  OPEN: "Open",
  IN_PROGRESS: "In progress",
  WAITING_FOR_CUSTOMER: "Waiting for customer",
  RESOLVED: "Resolved",
  CLOSED: "Closed",
}

const priorityLabels: Record<TicketPublic["priority"], string> = {
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
  URGENT: "Urgent",
}

const categoryLabels: Record<TicketPublic["category"], string> = {
  ACCOUNT: "Account",
  BILLING: "Billing",
  PRODUCT: "Product",
  BUG: "Bug",
  FEATURE_REQUEST: "Feature request",
  OTHER: "Other",
}

const statusVariants: Record<
  TicketPublic["status"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  OPEN: "secondary",
  IN_PROGRESS: "default",
  WAITING_FOR_CUSTOMER: "outline",
  RESOLVED: "secondary",
  CLOSED: "outline",
}

const priorityVariants: Record<
  TicketPublic["priority"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  LOW: "outline",
  MEDIUM: "secondary",
  HIGH: "default",
  URGENT: "destructive",
}

const formatDate = (value: string) =>
  new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))

export const ticketColumns: ColumnDef<TicketPublic>[] = [
  {
    accessorKey: "ticket_number",
    header: "Ticket",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">
        {row.original.ticket_number}
      </span>
    ),
  },
  {
    accessorKey: "title",
    header: "Title",
    cell: ({ row }) => (
      <div className="min-w-48 max-w-md">
        <p className="truncate font-medium text-foreground">
          {row.original.title}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {row.original.description}
        </p>
      </div>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge variant={statusVariants[row.original.status]}>
        {statusLabels[row.original.status]}
      </Badge>
    ),
  },
  {
    accessorKey: "priority",
    header: "Priority",
    cell: ({ row }) => (
      <Badge variant={priorityVariants[row.original.priority]}>
        {priorityLabels[row.original.priority]}
      </Badge>
    ),
  },
  {
    accessorKey: "category",
    header: "Category",
    cell: ({ row }) => categoryLabels[row.original.category],
  },
  {
    accessorKey: "assignee",
    header: "Assignee",
    cell: ({ row }) => {
      const assignee = row.original.assignee
      return assignee ? (
        <div className="max-w-40 truncate">
          <p className="truncate text-sm">
            {assignee.full_name?.trim() || assignee.email}
          </p>
          <p className="truncate text-xs text-muted-foreground">
            {assignee.email}
          </p>
        </div>
      ) : (
        <span className="text-muted-foreground">Unassigned</span>
      )
    },
  },
  {
    accessorKey: "updated_at",
    header: "Updated",
    cell: ({ row }) => (
      <span className="whitespace-nowrap text-sm text-muted-foreground">
        {formatDate(row.original.updated_at)}
      </span>
    ),
  },
]
