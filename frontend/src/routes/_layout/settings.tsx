import { createFileRoute } from "@tanstack/react-router"

import ChangePassword from "@/components/UserSettings/ChangePassword"
import UserInformation from "@/components/UserSettings/UserInformation"
import { ProviderSettings } from "@/components/AI/ProviderSettings"
import { AiWorkbench } from "@/components/AI/AiWorkbench"
import { KnowledgePanel } from "@/components/Knowledge/KnowledgePanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCurrentWorkspace } from "@/lib/workspaceQueries"

// 设置页保留资料和密码两个入口，删除账号能力已从当前契约移除。by AI.Coding
const tabsConfig = [
  { value: "my-profile", title: "我的资料", component: UserInformation },
  { value: "password", title: "密码", component: ChangePassword },
]

// AI Provider、知识库和 AI 工作台是 Workspace 管理能力，只对 Admin/Owner 暴露。by AI.Coding
const managerTabsConfig = [
  ...tabsConfig,
  { value: "ai-provider", title: "AI Provider", component: ProviderSettings },
  { value: "knowledge", title: "知识库", component: KnowledgePanel },
  { value: "ai-workbench", title: "AI 工作台", component: AiWorkbench },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  head: () => ({
    meta: [
      {
        title: "设置 - ResolveDesk",
      },
    ],
  }),
})

function UserSettings() {
  const { isManager } = useCurrentWorkspace()
  const visibleTabs = isManager ? managerTabsConfig : tabsConfig

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">账号设置</h1>
        <p className="text-muted-foreground">
          管理你的账号设置和偏好
        </p>
      </div>

      <Tabs defaultValue="my-profile">
        <TabsList>
          {visibleTabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.title}
            </TabsTrigger>
          ))}
        </TabsList>
        {visibleTabs.map((tab) => (
          <TabsContent key={tab.value} value={tab.value}>
            <tab.component />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
