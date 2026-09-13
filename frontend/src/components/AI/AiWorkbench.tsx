// AI 工作台最小演示：创建会话并显示 SSE 文本增量。by AI.Coding

import { useState } from "react"

import { conversationAction, createConversation, streamConversation } from "@/lib/aiApi"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

export function AiWorkbench() {
  const [workspaceId, setWorkspaceId] = useState(
    () => localStorage.getItem("resolvedesk.workspace_id") ?? "",
  )
  const [conversationId, setConversationId] = useState("")
  const [question, setQuestion] = useState("")
  const [answer, setAnswer] = useState("")
  const [running, setRunning] = useState(false)
  const [handedOff, setHandedOff] = useState(false)

  const send = async () => {
    if (!workspaceId || !question.trim()) return
    setRunning(true)
    setAnswer("")
    try {
      let activeConversationId = conversationId
      if (!activeConversationId) {
        const conversation = await createConversation(workspaceId)
        activeConversationId = conversation.id
        setConversationId(activeConversationId)
      }
      for await (const event of streamConversation(
        workspaceId,
        activeConversationId,
        question.trim(),
      )) {
        if (event.event === "message.delta") {
          setAnswer((current) => `${current}${String(event.data.text ?? "")}`)
        }
        if (event.event === "source.found") {
          setAnswer((current) => `${current}\n\n[来源] ${String(event.data.display_name ?? "")}`)
        }
      }
      setQuestion("")
    } finally {
      setRunning(false)
    }
  }

  const changeConversationState = async (action: "cancel" | "handoff" | "resume") => {
    if (!workspaceId || !conversationId) return
    await conversationAction(workspaceId, conversationId, action)
    setHandedOff(action === "handoff")
    if (action === "cancel") setRunning(false)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI 客服工作台</CardTitle>
        <p className="text-sm text-muted-foreground">
          SSE 实时输出；后端会把 Run、消息增量和终态事件持久化，便于审计和断线恢复。
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input
          value={workspaceId}
          onChange={(event) => {
            const value = event.target.value.trim()
            setWorkspaceId(value)
            localStorage.setItem("resolvedesk.workspace_id", value)
          }}
          placeholder="Workspace UUID"
        />
        <Textarea value={answer} readOnly placeholder="AI 回复会实时显示在这里" className="min-h-40" />
        <div className="flex flex-wrap gap-2">
          <Input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="例如：如何重置密码？"
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
          />
          <Button disabled={running || !workspaceId || !question.trim()} onClick={() => void send()}>
            {running ? "生成中…" : "发送"}
          </Button>
          {conversationId && (
            <>
              <Button variant="outline" disabled={!running} onClick={() => void changeConversationState("cancel")}>
                取消
              </Button>
              <Button variant="outline" onClick={() => void changeConversationState(handedOff ? "resume" : "handoff")}>
                {handedOff ? "恢复 AI" : "人工接管"}
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
