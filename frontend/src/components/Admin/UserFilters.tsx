import { RotateCcw, Search } from "lucide-react"

import type { UserRole } from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { UserFilterChange, UserListFilters } from "@/lib/userQueries"

const ALL = "__all__"

const roleOptions: Array<{ value: UserRole; label: string }> = [
  { value: "CUSTOMER", label: "Customer" },
  { value: "AGENT", label: "Agent" },
  { value: "ADMIN", label: "Admin" },
]

const activeOptions = [
  { value: "true", label: "Active" },
  { value: "false", label: "Inactive" },
] as const

const isUserRole = (value: string): value is UserRole =>
  roleOptions.some((option) => option.value === value)

// 用户目录筛选与工单筛选保持相同的 URL 受控交互。by AI.Coding
export function UserFilters({
  filters,
  onChange,
}: {
  filters: UserListFilters
  onChange: (change: UserFilterChange) => void
}) {
  const hasActiveFilters = Boolean(
    filters.query || filters.role || filters.isActive !== null,
  )

  return (
    <div className="flex w-full flex-wrap items-end gap-3 border-b bg-muted/20 p-4">
      <div className="relative min-w-56 flex-1">
        <label htmlFor="user-filter-query" className="sr-only">
          Search users
        </label>
        <Search
          aria-hidden="true"
          className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          id="user-filter-query"
          value={filters.query}
          onChange={(event) => onChange({ page: 1, query: event.target.value })}
          placeholder="Search name or email"
          className="pl-9"
        />
      </div>

      <div>
        <label htmlFor="user-filter-role" className="sr-only">
          Role
        </label>
        <Select
          value={filters.role ?? ALL}
          onValueChange={(value) =>
            onChange({
              page: 1,
              role: value === ALL || !isUserRole(value) ? null : value,
            })
          }
        >
          <SelectTrigger id="user-filter-role" className="w-36">
            <SelectValue placeholder="Role" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All roles</SelectItem>
            {roleOptions.map(({ value, label }) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <label htmlFor="user-filter-active" className="sr-only">
          Account status
        </label>
        <Select
          value={filters.isActive === null ? ALL : String(filters.isActive)}
          onValueChange={(value) =>
            onChange({
              page: 1,
              isActive: value === ALL ? null : value === "true",
            })
          }
        >
          <SelectTrigger id="user-filter-active" className="w-36">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            {activeOptions.map(({ value, label }) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {hasActiveFilters && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() =>
            onChange({
              page: 1,
              query: "",
              role: null,
              isActive: null,
            })
          }
          aria-label="Reset filters"
          title="Reset filters"
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}
