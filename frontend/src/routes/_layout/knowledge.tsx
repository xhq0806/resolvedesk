import { createFileRoute } from "@tanstack/react-router"

import { KnowledgePanel } from "@/components/Knowledge/KnowledgePanel"

export const Route = createFileRoute("/_layout/knowledge")({
  component: KnowledgeRoute,
  head: () => ({ meta: [{ title: "知识库 - ResolveDesk" }] }),
})

function KnowledgeRoute() {
  return <KnowledgePanel />
}
