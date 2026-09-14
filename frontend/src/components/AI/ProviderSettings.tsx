// Workspace AI Provider 配置面板，密钥只写入后端且不从状态中回显。by AI.Coding

import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  getProviderConfig,
  listToolPermissions,
  testProvider,
  updateToolPermissions,
  updateProviderConfig,
} from "@/lib/aiApi"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"

const workspaceKey = "resolvedesk.workspace_id"
const arkTemplate = {
  chatProvider: "volcengine-ark-responses" as const,
  embeddingProvider: "volcengine-ark" as const,
  baseUrl: "https://ark.cn-beijing.volces.com/api/v3",
  chatModel: "doubao-seed-2-1-pro-260628",
  embeddingModel: "doubao-embedding-vision-251215",
  embeddingDimension: 1024,
}

export function ProviderSettings() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [workspaceId, setWorkspaceId] = useState(
    () => localStorage.getItem(workspaceKey) ?? "",
  )
  const [apiKey, setApiKey] = useState("")
  const [chatUrl, setChatUrl] = useState("")
  const [chatModel, setChatModel] = useState("")
  const [embeddingUrl, setEmbeddingUrl] = useState("")
  const [embeddingModel, setEmbeddingModel] = useState("")
  const [embeddingDimension, setEmbeddingDimension] = useState("1024")
  const [enabled, setEnabled] = useState(false)
  const [tools, setTools] = useState<{ tool_name: string; enabled: boolean }[]>([])
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; message: string } | null>(null)

  const configQuery = useQuery({
    queryKey: ["ai-provider", workspaceId],
    queryFn: () => getProviderConfig(workspaceId),
    enabled: workspaceId.length > 0,
  })

  useEffect(() => {
    const config = configQuery.data
    if (!config) return
    setChatUrl(config.chat_base_url ?? "")
    setChatModel(config.chat_model)
    setEmbeddingUrl(config.embedding_base_url ?? "")
    setEmbeddingModel(config.embedding_model)
    setEmbeddingDimension(String(config.embedding_dimension))
    setEnabled(config.enabled)
  }, [configQuery.data])

  const saveMutation = useMutation({
    mutationFn: () =>
      updateProviderConfig(workspaceId, {
        chat_provider: arkTemplate.chatProvider,
        chat_base_url: chatUrl || undefined,
        chat_model: chatModel || undefined,
        embedding_provider: arkTemplate.embeddingProvider,
        embedding_base_url: embeddingUrl || undefined,
        embedding_model: embeddingModel || undefined,
        embedding_dimension: Number(embeddingDimension),
        api_key: apiKey || undefined,
        enabled,
      }),
    onSuccess: (data) => {
      setApiKey("")
      queryClient.setQueryData(["ai-provider", workspaceId], data)
      setFeedback({ kind: "success", message: "Provider 配置已保存。" })
      showSuccessToast("Provider 配置已保存，可以继续测试 Chat 或 Embedding。")
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : "保存 Provider 配置失败。"
      setFeedback({ kind: "error", message })
      showErrorToast(message)
    },
  })

  const testMutation = useMutation({
    mutationFn: (kind: "CHAT" | "EMBEDDING") => testProvider(workspaceId, kind),
    onSuccess: (data) => {
      const message = data.ok
        ? `${data.kind === "CHAT" ? "Chat" : "Embedding"} 连接成功（${data.latency_ms} ms）。`
        : `${data.message} (${data.code ?? "ERROR"})`
      setFeedback({ kind: data.ok ? "success" : "error", message })
      if (data.ok) showSuccessToast(message)
      else showErrorToast(message)
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : "Provider 测试失败。"
      setFeedback({ kind: "error", message })
      showErrorToast(message)
    },
  })

  const toolsQuery = useQuery({
    queryKey: ["ai-tools", workspaceId],
    queryFn: () => listToolPermissions(workspaceId),
    enabled: workspaceId.length > 0,
  })

  useEffect(() => {
    if (toolsQuery.data) setTools(toolsQuery.data)
  }, [toolsQuery.data])

  const toolsMutation = useMutation({
    mutationFn: () => updateToolPermissions(workspaceId, tools),
    onSuccess: (data) => setTools(data),
  })

  const applyArkTemplate = () => {
    setChatUrl(arkTemplate.baseUrl)
    setChatModel(arkTemplate.chatModel)
    setEmbeddingUrl(arkTemplate.baseUrl)
    setEmbeddingModel(arkTemplate.embeddingModel)
    setEmbeddingDimension(String(arkTemplate.embeddingDimension))
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Provider</CardTitle>
        <p className="text-sm text-muted-foreground">
          火山方舟配置会调用 Responses API 与多模态 Embedding，密钥只在服务端加密保存。
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" variant="outline" onClick={applyArkTemplate}>
            应用火山方舟模板
          </Button>
          <span className="text-sm text-muted-foreground">
            模板使用北京区域 API v3，Chat 模型来自你提供的接入示例。
          </span>
        </div>
        <div className="space-y-2">
          <Label htmlFor="workspace-id">Workspace ID</Label>
          <Input
            id="workspace-id"
            value={workspaceId}
            onChange={(event) => {
              const value = event.target.value.trim()
              setWorkspaceId(value)
              localStorage.setItem(workspaceKey, value)
            }}
            placeholder="粘贴当前 Workspace UUID"
          />
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="chat-url">Chat Base URL</Label>
            <Input id="chat-url" value={chatUrl} onChange={(e) => setChatUrl(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="chat-model">Chat Model</Label>
            <Input id="chat-model" value={chatModel} onChange={(e) => setChatModel(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="embedding-url">Embedding Base URL</Label>
            <Input id="embedding-url" value={embeddingUrl} onChange={(e) => setEmbeddingUrl(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="embedding-model">Embedding Model</Label>
            <Input id="embedding-model" value={embeddingModel} onChange={(e) => setEmbeddingModel(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="embedding-dimension">Embedding Dimension</Label>
            <Select value={embeddingDimension} onValueChange={setEmbeddingDimension}>
              <SelectTrigger id="embedding-dimension" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1024">1024</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="api-key">API Key</Label>
          <Input
            id="api-key"
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder={configQuery.data?.has_api_key ? "已配置（输入新值可替换）" : "仅发送到服务端"}
            autoComplete="new-password"
          />
        </div>
        <div className="flex items-center gap-3">
          <Checkbox checked={enabled} onCheckedChange={(value) => setEnabled(value === true)} id="provider-enabled" />
          <Label htmlFor="provider-enabled">启用 AI</Label>
        </div>
        <div className="space-y-2">
          <Label>AI 工具白名单</Label>
          <div className="grid gap-2 md:grid-cols-2">
            {tools.map((tool) => (
              <label key={tool.tool_name} className="flex items-center gap-2 rounded-md border p-2 text-sm">
                <Checkbox
                  checked={tool.enabled}
                  onCheckedChange={(value) =>
                    setTools((current) =>
                      current.map((item) =>
                        item.tool_name === tool.tool_name
                          ? { ...item, enabled: value === true }
                          : item,
                      ),
                    )
                  }
                />
                {tool.tool_name}
              </label>
            ))}
          </div>
          {tools.length > 0 && (
            <Button
              variant="outline"
              disabled={toolsMutation.isPending}
              onClick={() => toolsMutation.mutate()}
            >
              保存工具权限
            </Button>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={!workspaceId || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
            {saveMutation.isPending ? "保存中…" : "保存配置"}
          </Button>
          <Button
            variant="outline"
            disabled={!workspaceId || testMutation.isPending}
            onClick={() => testMutation.mutate("CHAT")}
          >
            {testMutation.isPending ? "测试中…" : "测试 Chat"}
          </Button>
          <Button
            variant="outline"
            disabled={!workspaceId || testMutation.isPending}
            onClick={() => testMutation.mutate("EMBEDDING")}
          >
            {testMutation.isPending ? "测试中…" : "测试 Embedding"}
          </Button>
          {feedback && (
            <span className="self-center text-sm text-muted-foreground">
              {feedback.message}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
