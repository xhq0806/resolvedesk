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

export const switchWorkspace = (workspaceId: string) => {
  localStorage.setItem(workspaceStorageKey, workspaceId)
  queryClient.clear()
  window.location.reload()
}
