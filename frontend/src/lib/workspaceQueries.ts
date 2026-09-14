// Workspace 列表和切换状态，所有切换都通过清缓存避免租户数据串读。by AI.Coding

import { useQuery } from "@tanstack/react-query"

import { queryClient } from "@/lib/queryClient"

export type WorkspaceSummary = {
  id: string
  name: string
  slug: string
  status: "ACTIVE" | "SUSPENDED"
  role: "OWNER" | "ADMIN" | "AGENT" | "CUSTOMER"
}

export const workspaceStorageKey = "resolvedesk.workspace_id"
export const workspaceKeys = {
  all: ["workspaces"] as const,
  list: () => [...workspaceKeys.all, "list"] as const,
}

export const listWorkspaces = async (): Promise<WorkspaceSummary[]> => {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL ?? ""}/api/v1/workspaces`,
    {
      headers: {
        Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
      },
    },
  )
  if (!response.ok) throw new Error(`Workspace 请求失败 (${response.status})`)
  return (await response.json()) as WorkspaceSummary[]
}

export const useWorkspaceList = () =>
  useQuery({
    queryKey: workspaceKeys.list(),
    queryFn: listWorkspaces,
    staleTime: 60_000,
  })

export const getCurrentWorkspaceId = () =>
  typeof localStorage === "undefined"
    ? ""
    : localStorage.getItem(workspaceStorageKey) ?? ""

export const isWorkspaceManagerRole = (
  role: WorkspaceSummary["role"] | null | undefined,
) => role === "OWNER" || role === "ADMIN"

export const getCurrentWorkspace = (
  workspaces: WorkspaceSummary[] | undefined,
) => {
  const activeWorkspaces =
    workspaces?.filter((workspace) => workspace.status === "ACTIVE") ?? []
  const currentId = getCurrentWorkspaceId()
  return (
    activeWorkspaces.find((workspace) => workspace.id === currentId) ??
    activeWorkspaces[0]
  )
}

export const useCurrentWorkspace = () => {
  const query = useWorkspaceList()
  const workspace = getCurrentWorkspace(query.data)
  return {
    ...query,
    workspace,
    role: workspace?.role,
    isManager: isWorkspaceManagerRole(workspace?.role),
  }
}

// 进入受保护页面前校正失效的租户 ID，避免数据库恢复或租户删除后全站请求继续携带旧值。by AI.Coding
export const ensureCurrentWorkspace = async (): Promise<string> => {
  const workspaces = await listWorkspaces()
  const activeWorkspaces = workspaces.filter(
    (workspace) => workspace.status === "ACTIVE",
  )
  const selected = getCurrentWorkspace(activeWorkspaces)
  const currentId = getCurrentWorkspaceId()

  if (selected && selected.id !== currentId) {
    localStorage.setItem(workspaceStorageKey, selected.id)
  }
  return selected?.id ?? ""
}

export const switchWorkspace = (workspaceId: string) => {
  localStorage.setItem(workspaceStorageKey, workspaceId)
  queryClient.clear()
  window.location.reload()
}
