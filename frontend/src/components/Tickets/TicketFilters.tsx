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
  { value: "OPEN", label: "待处理" },
  { value: "IN_PROGRESS", label: "处理中" },
  { value: "WAITING_FOR_CUSTOMER", label: "等待客户" },
  { value: "RESOLVED", label: "已解决" },
  { value: "CLOSED", label: "已关闭" },
]

const priorityOptions: Array<{ value: TicketPriority; label: string }> = [
  { value: "LOW", label: "低" },
  { value: "MEDIUM", label: "中" },
  { value: "HIGH", label: "高" },
  { value: "URGENT", label: "紧急" },
]

const categoryOptions: Array<{ value: TicketCategory; label: string }> = [
  { value: "ACCOUNT", label: "账号问题" },
  { value: "BILLING", label: "账单问题" },
  { value: "PRODUCT", label: "产品咨询" },
  { value: "BUG", label: "缺陷反馈" },
  { value: "FEATURE_REQUEST", label: "功能建议" },
  { value: "OTHER", label: "其他" },
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
          搜索工单
        </label>
        <Search
          aria-hidden="true"
          className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          id="ticket-filter-query"
          value={filters.query}
          onChange={(event) => onChange({ page: 1, query: event.target.value })}
          placeholder="按标题或工单编号搜索"
          className="pl-9"
        />
      </div>

      {showStatus && (
        <div>
          <label htmlFor="ticket-filter-status" className="sr-only">
            状态
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
              <SelectValue placeholder="状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部状态</SelectItem>
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
          优先级
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
            <SelectValue placeholder="优先级" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>全部优先级</SelectItem>
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
          分类
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
            <SelectValue placeholder="分类" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>全部分类</SelectItem>
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
            负责人
          </label>
          <Select
            value={filters.assigneeId ?? ALL}
            onValueChange={(value) =>
              onChange({ page: 1, assigneeId: value === ALL ? null : value })
            }
          >
            <SelectTrigger id="ticket-filter-assignee" className="w-44">
              <SelectValue placeholder="负责人" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部负责人</SelectItem>
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
          aria-label="重置筛选条件"
          title="重置筛选条件"
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}
