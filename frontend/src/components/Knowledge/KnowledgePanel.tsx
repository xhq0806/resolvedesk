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
import { useCurrentWorkspace } from "@/lib/workspaceQueries"

export function KnowledgePanel() {
  const [file, setFile] = useState<File | null>(null)
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const { workspace, isManager } = useCurrentWorkspace()
  const workspaceId = workspace?.id ?? ""
  const documentsQuery = useQuery({
    queryKey: ["knowledge-documents", workspaceId],
    queryFn: () => listKnowledgeDocuments(workspaceId),
    enabled: isManager && workspaceId.length > 0,
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
        <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
          当前 Workspace：{workspace?.name ?? "未选择"}
        </div>
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
