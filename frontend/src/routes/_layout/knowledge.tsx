import { createFileRoute } from "@tanstack/react-router"

import { KnowledgePanel } from "@/components/Knowledge/KnowledgePanel"
import { requireWorkspaceManager } from "@/lib/routeGuards"

export const Route = createFileRoute("/_layout/knowledge")({
  component: KnowledgeRoute,
  beforeLoad: requireWorkspaceManager(),
  head: () => ({ meta: [{ title: "知识库 - ResolveDesk" }] }),
})

function KnowledgeRoute() {
  return <KnowledgePanel />
}
