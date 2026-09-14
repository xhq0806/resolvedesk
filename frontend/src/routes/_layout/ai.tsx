import { createFileRoute } from "@tanstack/react-router"

import { AiWorkbench } from "@/components/AI/AiWorkbench"
import { requireWorkspaceManager } from "@/lib/routeGuards"

export const Route = createFileRoute("/_layout/ai")({
  component: AiRoute,
  beforeLoad: requireWorkspaceManager(),
  head: () => ({ meta: [{ title: "AI 工作台 - ResolveDesk" }] }),
})

function AiRoute() {
  return <AiWorkbench />
}
