// AI Provider、知识库和会话 API 的轻量封装，等待 OpenAPI 客户端重新生成后可平滑替换。by AI.Coding

export type ProviderConfig = {
  id: string
  workspace_id: string
  chat_provider: "openai-compatible" | "volcengine-ark-responses"
  chat_base_url: string | null
  chat_model: string
  embedding_provider: "openai-compatible" | "volcengine-ark"
  embedding_base_url: string | null
  embedding_model: string
  embedding_dimension: number
  has_api_key: boolean
  masked_api_key: string | null
  enabled: boolean
  updated_at: string
}

export type ProviderPatch = Partial<
  Pick<
    ProviderConfig,
    | "chat_provider"
    | "chat_base_url"
    | "chat_model"
    | "embedding_provider"
    | "embedding_base_url"
    | "embedding_model"
    | "embedding_dimension"
    | "enabled"
  >
> & {
  api_key?: string
  clear_api_key?: boolean
}

export type KnowledgeDocument = {
  id: string
  workspace_id: string
  display_name: string
  mime_type: string
  size_bytes: number
  sha256: string
  status: "PROCESSING" | "READY" | "FAILED" | "DELETED"
  version: number
  error_code: string | null
  created_at: string
}

const apiUrl = () => import.meta.env.VITE_API_URL ?? ""

const headersFor = (workspaceId: string, json = false): HeadersInit => ({
  ...(json ? { "Content-Type": "application/json" } : {}),
  Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
  "X-Workspace-ID": workspaceId,
})

const requestJson = async <T>(
  workspaceId: string,
  path: string,
  init: RequestInit = {},
): Promise<T> => {
  const response = await fetch(`${apiUrl()}${path}`, {
    ...init,
    headers: {
      ...headersFor(workspaceId, Boolean(init.body)),
      ...init.headers,
    },
  })
  if (!response.ok) {
    throw new Error(`请求失败 (${response.status})`)
  }
  return (await response.json()) as T
}

export const getProviderConfig = (workspaceId: string) =>
  requestJson<ProviderConfig>(
    workspaceId,
    `/api/v1/workspaces/${workspaceId}/ai/provider`,
  )

export const updateProviderConfig = (
  workspaceId: string,
  patch: ProviderPatch,
) =>
  requestJson<ProviderConfig>(
    workspaceId,
    `/api/v1/workspaces/${workspaceId}/ai/provider`,
    { method: "PATCH", body: JSON.stringify(patch) },
  )

export const testProvider = (workspaceId: string, kind: "CHAT" | "EMBEDDING") =>
  requestJson<{ ok: boolean; code?: string; message: string }>(
    workspaceId,
    `/api/v1/workspaces/${workspaceId}/ai/provider/test`,
    { method: "POST", body: JSON.stringify({ kind }) },
  )

export type ToolPermission = {
  tool_name: string
  enabled: boolean
}

export const listToolPermissions = (workspaceId: string) =>
  requestJson<ToolPermission[]>(
    workspaceId,
    `/api/v1/workspaces/${workspaceId}/ai/tools`,
  )

export const updateToolPermissions = (
  workspaceId: string,
  permissions: ToolPermission[],
) =>
  requestJson<ToolPermission[]>(
    workspaceId,
    `/api/v1/workspaces/${workspaceId}/ai/tools`,
    { method: "PATCH", body: JSON.stringify(permissions) },
  )

export const listKnowledgeDocuments = (workspaceId: string) =>
  requestJson<KnowledgeDocument[]>(
    workspaceId,
    `/api/v1/workspaces/${workspaceId}/knowledge/documents`,
  )

export const uploadKnowledgeDocument = async (
  workspaceId: string,
  file: File,
): Promise<KnowledgeDocument> => {
  const form = new FormData()
  form.append("file", file)
  const response = await fetch(
    `${apiUrl()}/api/v1/workspaces/${workspaceId}/knowledge/documents`,
    { method: "POST", headers: headersFor(workspaceId), body: form },
  )
  if (!response.ok) throw new Error(`上传失败 (${response.status})`)
  return (await response.json()) as KnowledgeDocument
}

export type Conversation = {
  id: string
  workspace_id: string
  ticket_id: string | null
  mode: string
  status: string
  handed_off: boolean
}

export const createConversation = (workspaceId: string, ticketId?: string) =>
  requestJson<Conversation>(
    workspaceId,
    `/api/v1/workspaces/${workspaceId}/conversations`,
    {
      method: "POST",
      body: JSON.stringify({ ticket_id: ticketId || undefined }),
    },
  )

export const conversationAction = (
  workspaceId: string,
  conversationId: string,
  action: "cancel" | "handoff" | "resume",
) =>
  requestJson<Conversation>(
    workspaceId,
    `/api/v1/workspaces/${workspaceId}/conversations/${conversationId}/${action}`,
    { method: "POST" },
  )

export const retryKnowledgeDocument = (
  workspaceId: string,
  documentId: string,
) =>
  requestJson<unknown>(
    workspaceId,
    `/api/v1/workspaces/${workspaceId}/knowledge/documents/${documentId}/retry`,
    { method: "POST" },
  )

export const deleteKnowledgeDocument = async (
  workspaceId: string,
  documentId: string,
) => {
  const response = await fetch(
    `${apiUrl()}/api/v1/workspaces/${workspaceId}/knowledge/documents/${documentId}`,
    { method: "DELETE", headers: headersFor(workspaceId) },
  )
  if (!response.ok) throw new Error(`删除失败 (${response.status})`)
}

export const streamConversation = async function* (
  workspaceId: string,
  conversationId: string,
  content: string,
): AsyncGenerator<{ event: string; data: Record<string, unknown> }> {
  const response = await fetch(
    `${apiUrl()}/api/v1/workspaces/${workspaceId}/conversations/${conversationId}/messages/stream`,
    {
      method: "POST",
      headers: headersFor(workspaceId, true),
      body: JSON.stringify({
        content,
        client_message_id: crypto.randomUUID(),
      }),
    },
  )
  if (!response.ok || !response.body) {
    throw new Error(`聊天请求失败 (${response.status})`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
      const frames = buffer.split("\n\n")
      buffer = frames.pop() ?? ""
      for (const frame of frames) {
        const event = frame.match(/^event: (.+)$/m)?.[1]
        const data = frame.match(/^data: (.+)$/m)?.[1]
        if (event && data) {
          yield { event, data: JSON.parse(data) as Record<string, unknown> }
        }
      }
      if (done) break
    }
  } finally {
    reader.releaseLock()
  }
}
