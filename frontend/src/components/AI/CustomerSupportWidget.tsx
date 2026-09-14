// Customer 在线咨询浮窗，提供 AI Agent 回答和转人工入口。by AI.Coding

import { useMemo, useState } from "react"
import { Bot, ChevronUp, MoreHorizontal, Send, X } from "lucide-react"

import {
  getOrCreateCustomerConversation,
  handoffConversationToTicket,
  streamCustomerConversation,
  type Conversation,
} from "@/lib/aiApi"
import { useCurrentWorkspace } from "@/lib/workspaceQueries"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import useCustomToast from "@/hooks/useCustomToast"

type ChatMessage = {
  id: string
  role: "user" | "assistant"
  content: string
}

type SourcePreview = {
  id: string
  displayName: string
  preview: string
}

export function CustomerSupportWidget() {
  const { workspace, role } = useCurrentWorkspace()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [open, setOpen] = useState(false)
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sources, setSources] = useState<SourcePreview[]>([])
  const [input, setInput] = useState("")
  const [running, setRunning] = useState(false)
  const [handoffPending, setHandoffPending] = useState(false)
  const visible = role === "CUSTOMER" && Boolean(workspace?.id)

  const assistantDraftId = useMemo(() => crypto.randomUUID(), [messages.length])
  if (!visible) return null

  const openPanel = async () => {
    setOpen(true)
    if (conversation || !workspace?.id) return
    try {
      setConversation(await getOrCreateCustomerConversation(workspace.id))
    } catch (error) {
      showErrorToast(error instanceof Error ? error.message : "在线咨询暂不可用")
    }
  }

  const sendMessage = async () => {
    const content = input.trim()
    if (!workspace?.id || !content || running) return
    setInput("")
    setRunning(true)
    setSources([])
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content },
      { id: assistantDraftId, role: "assistant", content: "" },
    ])
    try {
      const activeConversation =
        conversation ?? (await getOrCreateCustomerConversation(workspace.id))
      setConversation(activeConversation)
      for await (const event of streamCustomerConversation(workspace.id, content)) {
        if (event.event === "message.delta") {
          const text = typeof event.data.text === "string" ? event.data.text : ""
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantDraftId
                ? { ...message, content: message.content + text }
              : message,
            ),
          )
        }
        if (event.event === "source.found") {
          const chunkId =
            typeof event.data.chunk_id === "string"
              ? event.data.chunk_id
              : crypto.randomUUID()
          const displayName =
            typeof event.data.display_name === "string"
              ? event.data.display_name
              : "知识库来源"
          const preview =
            typeof event.data.preview === "string" ? event.data.preview : ""
          setSources((current) => [
            ...current.filter((source) => source.id !== chunkId),
            { id: chunkId, displayName, preview },
          ])
        }
      }
    } catch (error) {
      showErrorToast(error instanceof Error ? error.message : "发送失败")
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantDraftId && !message.content
            ? { ...message, content: "在线咨询暂时不可用，请稍后再试或转人工。" }
            : message,
        ),
      )
    } finally {
      setRunning(false)
    }
  }

  const requestHandoff = async () => {
    if (!workspace?.id || !conversation || handoffPending) return
    setHandoffPending(true)
    try {
      const result = await handoffConversationToTicket(
        workspace.id,
        conversation.id,
        "客户从在线咨询请求转人工。",
      )
      setConversation(result.conversation)
      const status = result.assigned ? "已分派人工客服" : "已进入客服队列"
      showSuccessToast(`工单 ${result.ticket_number} ${status}`)
    } catch (error) {
      showErrorToast(error instanceof Error ? error.message : "转人工失败")
    } finally {
      setHandoffPending(false)
    }
  }

  return (
    <>
      {!open && (
        <Button
          className="fixed right-6 bottom-8 z-40 h-44 w-16 rounded-full shadow-lg"
          onClick={openPanel}
        >
          <span className="flex flex-col items-center gap-3">
            <Bot className="size-6" />
            <span className="[writing-mode:vertical-rl] text-base tracking-normal">
              在线咨询
            </span>
          </span>
        </Button>
      )}
      {open && (
        <section className="fixed right-6 bottom-8 z-40 flex h-[min(720px,calc(100vh-4rem))] w-[min(420px,calc(100vw-2rem))] flex-col rounded-lg border bg-background shadow-2xl">
          <header className="flex h-14 items-center justify-between border-b px-4">
            <div className="flex items-center gap-2">
              <Bot className="size-5 text-primary" />
              <h2 className="text-base font-semibold">在线咨询</h2>
            </div>
            <div className="flex items-center gap-1">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" onClick={requestHandoff}>
                      <MoreHorizontal className="size-5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>转人工</TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Button variant="ghost" size="icon" onClick={() => setOpen(false)}>
                <X className="size-5" />
              </Button>
            </div>
          </header>
          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {messages.length === 0 && (
              <div className="space-y-3">
                <PromptButton label="账号充值后，为什么额度已用完？" onPick={setInput} />
                <PromptButton label="如何诊断 API 接口返回的报错信息？" onPick={setInput} />
                <PromptButton label="Agent Plan 的套餐用量如何查询？" onPick={setInput} />
              </div>
            )}
            {messages.map((message) => (
              <div
                key={message.id}
                className={
                  message.role === "user"
                    ? "ml-auto max-w-[82%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground"
                    : "mr-auto max-w-[88%] rounded-lg bg-muted px-3 py-2 text-sm"
                }
              >
                {message.content || "正在回复..."}
              </div>
            ))}
            {sources.length > 0 && (
              <div className="mr-auto max-w-[88%] space-y-2 rounded-lg border bg-background px-3 py-2 text-xs text-muted-foreground">
                <div className="font-medium text-foreground">参考来源</div>
                {sources.slice(0, 3).map((source) => (
                  <div key={source.id} className="space-y-1">
                    <div className="truncate font-medium text-foreground">
                      {source.displayName}
                    </div>
                    {source.preview && (
                      <p className="line-clamp-2">{source.preview}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="border-t p-3">
            <div className="mb-2 flex items-center justify-between">
              <Badge variant="secondary">AI 生成，仅供参考</Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={requestHandoff}
                disabled={!conversation || handoffPending}
              >
                <ChevronUp className="size-4" />
                转人工
              </Button>
            </div>
            <div className="flex items-end gap-2">
              <Textarea
                className="min-h-20 resize-none"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="您可以使用“产品+问题”描述问题"
              />
              <Button
                size="icon"
                onClick={sendMessage}
                disabled={!input.trim() || running}
              >
                <Send className="size-5" />
              </Button>
            </div>
          </div>
        </section>
      )}
    </>
  )
}

function PromptButton({
  label,
  onPick,
}: {
  label: string
  onPick: (value: string) => void
}) {
  return (
    <button
      type="button"
      className="flex w-full items-center justify-between rounded-md border px-3 py-3 text-left text-sm hover:bg-muted"
      onClick={() => onPick(label)}
    >
      <span>{label}</span>
      <ChevronUp className="size-4 rotate-90 text-muted-foreground" />
    </button>
  )
}
