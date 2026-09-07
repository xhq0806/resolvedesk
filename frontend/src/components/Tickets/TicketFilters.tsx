import { RotateCcw, Search } from "lucide-react"

import type {
  TicketCategory,
  TicketPriority,
  TicketStatus,
  UserSummary,
} from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { TicketFilterChange, TicketListFilters } from "@/lib/ticketQueries"

const ALL = "__all__"

const statusOptions: Array<{ value: TicketStatus; label: string }> = [
  { value: "OPEN", label: "Open" },
  { value: "IN_PROGRESS", label: "In progress" },
  { value: "WAITING_FOR_CUSTOMER", label: "Waiting for customer" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "CLOSED", label: "Closed" },
]

const priorityOptions: Array<{ value: TicketPriority; label: string }> = [
  { value: "LOW", label: "Low" },
  { value: "MEDIUM", label: "Medium" },
  { value: "HIGH", label: "High" },
  { value: "URGENT", label: "Urgent" },
]

const categoryOptions: Array<{ value: TicketCategory; label: string }> = [
  { value: "ACCOUNT", label: "Account" },
  { value: "BILLING", label: "Billing" },
  { value: "PRODUCT", label: "Product" },
  { value: "BUG", label: "Bug" },
  { value: "FEATURE_REQUEST", label: "Feature request" },
  { value: "OTHER", label: "Other" },
]

const isTicketStatus = (value: string): value is TicketStatus =>
  statusOptions.some((option) => option.value === value)

const isTicketPriority = (value: string): value is TicketPriority =>
  priorityOptions.some((option) => option.value === value)

const isTicketCategory = (value: string): value is TicketCategory =>
  categoryOptions.some((option) => option.value === value)

type TicketAssigneeOption = Pick<UserSummary, "id" | "email" | "full_name">

interface TicketFiltersProps {
  filters: TicketListFilters
  onChange: (change: TicketFilterChange) => void
  assignees?: TicketAssigneeOption[]
  showStatus?: boolean
}

const getAssigneeLabel = (assignee: TicketAssigneeOption) =>
  assignee.full_name?.trim() || assignee.email

export function TicketFilters({
  filters,
  onChange,
  assignees = [],
  showStatus = true,
}: TicketFiltersProps) {
  const hasActiveFilters = Boolean(
    filters.query ||
      filters.status ||
      filters.priority ||
      filters.category ||
      filters.assigneeId,
  )

  const resetFilters = () => {
    onChange({
      page: 1,
      query: "",
      status: null,
      priority: null,
      category: null,
      assigneeId: null,
    })
  }

  return (
    <div className="flex w-full flex-wrap items-end gap-3 border-b bg-muted/20 p-4">
      <div className="relative min-w-56 flex-1">
        <label htmlFor="ticket-filter-query" className="sr-only">
          Search tickets
        </label>
        <Search
          aria-hidden="true"
          className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          id="ticket-filter-query"
          value={filters.query}
          onChange={(event) => onChange({ page: 1, query: event.target.value })}
          placeholder="Search by title or ticket number"
          className="pl-9"
        />
      </div>

      {showStatus && (
        <div>
          <label htmlFor="ticket-filter-status" className="sr-only">
            Status
          </label>
          <Select
            value={filters.status ?? ALL}
            onValueChange={(value) => {
              onChange({
                page: 1,
                status: value === ALL || !isTicketStatus(value) ? null : value,
              })
            }}
          >
            <SelectTrigger id="ticket-filter-status" className="w-44">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {statusOptions.map(({ value, label }) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <div>
        <label htmlFor="ticket-filter-priority" className="sr-only">
          Priority
        </label>
        <Select
          value={filters.priority ?? ALL}
          onValueChange={(value) => {
            onChange({
              page: 1,
              priority:
                value === ALL || !isTicketPriority(value) ? null : value,
            })
          }}
        >
          <SelectTrigger id="ticket-filter-priority" className="w-32">
            <SelectValue placeholder="Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All priorities</SelectItem>
            {priorityOptions.map(({ value, label }) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <label htmlFor="ticket-filter-category" className="sr-only">
          Category
        </label>
        <Select
          value={filters.category ?? ALL}
          onValueChange={(value) => {
            onChange({
              page: 1,
              category:
                value === ALL || !isTicketCategory(value) ? null : value,
            })
          }}
        >
          <SelectTrigger id="ticket-filter-category" className="w-40">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All categories</SelectItem>
            {categoryOptions.map(({ value, label }) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {assignees.length > 0 && (
        <div>
          <label htmlFor="ticket-filter-assignee" className="sr-only">
            Assignee
          </label>
          <Select
            value={filters.assigneeId ?? ALL}
            onValueChange={(value) =>
              onChange({ page: 1, assigneeId: value === ALL ? null : value })
            }
          >
            <SelectTrigger id="ticket-filter-assignee" className="w-44">
              <SelectValue placeholder="Assignee" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All assignees</SelectItem>
              {assignees.map((assignee) => (
                <SelectItem key={assignee.id} value={assignee.id}>
                  {getAssigneeLabel(assignee)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {hasActiveFilters && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={resetFilters}
          aria-label="Reset filters"
          title="Reset filters"
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}
