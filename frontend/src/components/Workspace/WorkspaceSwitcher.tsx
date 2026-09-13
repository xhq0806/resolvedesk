// 侧栏 Workspace 切换器，切换前清理所有查询缓存。by AI.Coding

import { useEffect, useState } from "react"

import { getCurrentWorkspaceId, switchWorkspace, useWorkspaceList } from "@/lib/workspaceQueries"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export function WorkspaceSwitcher() {
  const workspacesQuery = useWorkspaceList()
  const [currentId, setCurrentId] = useState(getCurrentWorkspaceId)

  useEffect(() => {
    if (!currentId && workspacesQuery.data?.[0]) {
      const firstId = workspacesQuery.data[0].id
      setCurrentId(firstId)
      localStorage.setItem("resolvedesk.workspace_id", firstId)
    }
  }, [currentId, workspacesQuery.data])

  if (!workspacesQuery.data?.length) return null

  return (
    <Select
      value={currentId || workspacesQuery.data[0].id}
      onValueChange={(value) => {
        setCurrentId(value)
        switchWorkspace(value)
      }}
    >
      <SelectTrigger className="w-full">
        <SelectValue placeholder="选择 Workspace" />
      </SelectTrigger>
      <SelectContent>
        {workspacesQuery.data
          .filter((workspace) => workspace.status === "ACTIVE")
          .map((workspace) => (
            <SelectItem key={workspace.id} value={workspace.id}>
              {workspace.name} · {workspace.role}
            </SelectItem>
          ))}
      </SelectContent>
    </Select>
  )
}
