import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table"
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Loader2,
} from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  pagination?: {
    pageIndex: number
    pageSize: number
    totalCount: number
    onPageChange: (pageIndex: number) => void
    onPageSizeChange: (pageSize: number) => void
  }
  toolbar?: ReactNode
  emptyState?: ReactNode
  isFetching?: boolean
}

export function DataTable<TData, TValue>({
  columns,
  data,
  pagination,
  toolbar,
  emptyState,
  isFetching = false,
}: DataTableProps<TData, TValue>) {
  const isServerPaginated = pagination !== undefined
  const serverPageCount = pagination
    ? Math.ceil(pagination.totalCount / pagination.pageSize)
    : undefined

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    ...(isServerPaginated
      ? {
          manualPagination: true,
          pageCount: serverPageCount,
          state: {
            pagination: {
              pageIndex: pagination.pageIndex,
              pageSize: pagination.pageSize,
            },
          },
        }
      : { getPaginationRowModel: getPaginationRowModel() }),
  })

  const currentPageIndex =
    pagination?.pageIndex ?? table.getState().pagination.pageIndex
  const currentPageSize =
    pagination?.pageSize ?? table.getState().pagination.pageSize
  const totalCount = pagination?.totalCount ?? data.length
  const pageCount = pagination ? (serverPageCount ?? 0) : table.getPageCount()
  const firstEntry =
    totalCount === 0 ? 0 : currentPageIndex * currentPageSize + 1
  const lastEntry = Math.min(
    (currentPageIndex + 1) * currentPageSize,
    totalCount,
  )

  const goToPage = (pageIndex: number) => {
    if (pagination) {
      pagination.onPageChange(pageIndex)
      return
    }

    table.setPageIndex(pageIndex)
  }

  const changePageSize = (pageSize: number) => {
    if (pagination) {
      pagination.onPageSizeChange(pageSize)
      return
    }

    table.setPageSize(pageSize)
  }

  return (
    <div className="flex flex-col gap-4">
      {toolbar && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {toolbar}
        </div>
      )}

      <div className="relative">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent">
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow className="hover:bg-transparent">
                <TableCell
                  colSpan={columns.length}
                  className="h-32 text-center text-muted-foreground"
                >
              {emptyState ?? "没有找到结果。"}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>

        {isFetching && (
          <div
            className="absolute inset-0 flex items-center justify-center bg-background/70 backdrop-blur-[1px]"
            role="status"
            aria-label="正在加载"
          >
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>正在加载……</span>
            </div>
          </div>
        )}
      </div>

      {pageCount > 1 && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 border-t bg-muted/20">
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="text-sm text-muted-foreground">
              显示第 {firstEntry}–{lastEntry} 条，共{" "}
              <span className="font-medium text-foreground">{totalCount}</span>{" "}
              条
            </div>
            <div className="flex items-center gap-x-2">
              <p className="text-sm text-muted-foreground">每页行数</p>
              <Select
                value={`${currentPageSize}`}
                onValueChange={(value) => {
                  changePageSize(Number(value))
                }}
              >
                <SelectTrigger className="h-8 w-[70px]">
                  <SelectValue placeholder={currentPageSize} />
                </SelectTrigger>
                <SelectContent side="top">
                  {[5, 10, 25, 50].map((pageSize) => (
                    <SelectItem key={pageSize} value={`${pageSize}`}>
                      {pageSize}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex items-center gap-x-6">
            <div className="flex items-center gap-x-1 text-sm text-muted-foreground">
              <span>第</span>
              <span className="font-medium text-foreground">
                {currentPageIndex + 1}
              </span>
              <span>页，共</span>
              <span className="font-medium text-foreground">{pageCount}</span>
            </div>

            <div className="flex items-center gap-x-1">
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goToPage(0)}
                disabled={!table.getCanPreviousPage()}
              >
                <span className="sr-only">跳转到第一页</span>
                <ChevronsLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goToPage(currentPageIndex - 1)}
                disabled={!table.getCanPreviousPage()}
              >
                <span className="sr-only">跳转到上一页</span>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goToPage(currentPageIndex + 1)}
                disabled={!table.getCanNextPage()}
              >
                <span className="sr-only">跳转到下一页</span>
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goToPage(pageCount - 1)}
                disabled={!table.getCanNextPage()}
              >
                <span className="sr-only">跳转到最后一页</span>
                <ChevronsRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
