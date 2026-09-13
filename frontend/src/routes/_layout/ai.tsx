import { createFileRoute } from "@tanstack/react-router"

import { AiWorkbench } from "@/components/AI/AiWorkbench"

export const Route = createFileRoute("/_layout/ai")({
  component: AiRoute,
  head: () => ({ meta: [{ title: "AI 工作台 - ResolveDesk" }] }),
})

function AiRoute() {
  return <AiWorkbench />
}
