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

const workspaceKey = "resolvedesk.workspace_id"

export function ProviderSettings() {
  const queryClient = useQueryClient()
  const [workspaceId, setWorkspaceId] = useState(
    () => localStorage.getItem(workspaceKey) ?? "",
  )
  const [apiKey, setApiKey] = useState("")
  const [chatUrl, setChatUrl] = useState("")
  const [chatModel, setChatModel] = useState("")
  const [embeddingUrl, setEmbeddingUrl] = useState("")
  const [embeddingModel, setEmbeddingModel] = useState("")
  const [enabled, setEnabled] = useState(false)
  const [tools, setTools] = useState<{ tool_name: string; enabled: boolean }[]>([])

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
    setEnabled(config.enabled)
  }, [configQuery.data])

  const saveMutation = useMutation({
    mutationFn: () =>
      updateProviderConfig(workspaceId, {
        chat_base_url: chatUrl || undefined,
        chat_model: chatModel || undefined,
        embedding_base_url: embeddingUrl || undefined,
        embedding_model: embeddingModel || undefined,
        api_key: apiKey || undefined,
        enabled,
      }),
    onSuccess: (data) => {
      setApiKey("")
      queryClient.setQueryData(["ai-provider", workspaceId], data)
    },
  })

  const testMutation = useMutation({
    mutationFn: (kind: "CHAT" | "EMBEDDING") => testProvider(workspaceId, kind),
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Provider</CardTitle>
        <p className="text-sm text-muted-foreground">
          OpenAI-compatible Chat/Embedding 配置，密钥只在服务端加密保存。
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
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
            保存配置
          </Button>
          <Button
            variant="outline"
            disabled={!workspaceId || testMutation.isPending}
            onClick={() => testMutation.mutate("CHAT")}
          >
            测试 Chat
          </Button>
          <Button
            variant="outline"
            disabled={!workspaceId || testMutation.isPending}
            onClick={() => testMutation.mutate("EMBEDDING")}
          >
            测试 Embedding
          </Button>
          {testMutation.data && (
            <span className="self-center text-sm text-muted-foreground">
              {testMutation.data.ok ? "连接成功" : `${testMutation.data.message} (${testMutation.data.code ?? "ERROR"})`}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
