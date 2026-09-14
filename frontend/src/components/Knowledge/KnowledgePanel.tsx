// Workspace 知识库管理面板，展示上传和摄取状态。by AI.Coding

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  deleteKnowledgeDocument,
  listKnowledgeDocuments,
  retryKnowledgeDocument,
  uploadKnowledgeDocument,
} from "@/lib/aiApi"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import useCustomToast from "@/hooks/useCustomToast"

export function KnowledgePanel() {
  const [workspaceId, setWorkspaceId] = useState(
    () => localStorage.getItem("resolvedesk.workspace_id") ?? "",
  )
  const [file, setFile] = useState<File | null>(null)
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const documentsQuery = useQuery({
    queryKey: ["knowledge-documents", workspaceId],
    queryFn: () => listKnowledgeDocuments(workspaceId),
    enabled: workspaceId.length > 0,
  })
  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("请选择文档")
      return uploadKnowledgeDocument(workspaceId, file)
    },
    onSuccess: () => {
      setFile(null)
      queryClient.invalidateQueries({ queryKey: ["knowledge-documents", workspaceId] })
      showSuccessToast("文档已上传，后台正在解析并写入向量库。")
    },
    onError: (error) => {
      // 让用户在上传失败时看到可操作的后端错误，而不是无反馈。by AI.Coding
      showErrorToast(error instanceof Error ? error.message : "上传失败")
    },
  })
  const actionMutation = useMutation({
    mutationFn: (input: { id: string; action: "retry" | "delete" }) =>
      input.action === "retry"
        ? retryKnowledgeDocument(workspaceId, input.id)
        : deleteKnowledgeDocument(workspaceId, input.id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["knowledge-documents", workspaceId] }),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>知识库 RAG</CardTitle>
        <p className="text-sm text-muted-foreground">
          支持 PDF、DOCX、Markdown 和纯文本；上传后由后台任务解析、切块并写入向量库。
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <input
          className="w-full rounded-md border bg-background p-2 text-sm"
          value={workspaceId}
          onChange={(event) => {
            const value = event.target.value.trim()
            setWorkspaceId(value)
            localStorage.setItem("resolvedesk.workspace_id", value)
          }}
          placeholder="Workspace UUID"
        />
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="file"
            accept=".pdf,.docx,.md,.markdown,.txt"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <Button disabled={!workspaceId || !file || uploadMutation.isPending} onClick={() => uploadMutation.mutate()}>
            上传文档
          </Button>
        </div>
        <div className="space-y-2">
          {(documentsQuery.data ?? []).map((document) => (
            <div key={document.id} className="flex items-center justify-between gap-3 rounded-md border p-3 text-sm">
              <span className="min-w-0 truncate">{document.display_name}</span>
              <div className="flex items-center gap-2">
                <Badge variant={document.status === "READY" ? "default" : "secondary"}>{document.status}</Badge>
                {document.status === "FAILED" && (
                  <Button size="sm" variant="outline" onClick={() => actionMutation.mutate({ id: document.id, action: "retry" })}>
                    重试
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => actionMutation.mutate({ id: document.id, action: "delete" })}>
                  删除
                </Button>
              </div>
            </div>
          ))}
          {workspaceId && documentsQuery.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">还没有知识文档。</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
