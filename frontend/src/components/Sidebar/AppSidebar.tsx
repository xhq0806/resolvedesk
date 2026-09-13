import { BookOpen, Home, Inbox, ListTodo, MessageSquare, Settings, Users } from "lucide-react"

import type { UserRole } from "@/client"
import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { WorkspaceSwitcher } from "@/components/Workspace/WorkspaceSwitcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { getUserRole } from "@/lib/routeGuards"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Home, title: "工作台", path: "/" },
  { icon: MessageSquare, title: "AI 工作台", path: "/ai" },
  { icon: BookOpen, title: "知识库", path: "/knowledge" },
  { icon: Settings, title: "设置", path: "/settings" },
]
const itemsByRole: Record<UserRole, Item[]> = {
  CUSTOMER: [
    ...baseItems,
    { icon: Inbox, title: "我的工单", path: "/tickets" },
  ],
  AGENT: [...baseItems, { icon: ListTodo, title: "客服队列", path: "/queue" }],
  ADMIN: [
    ...baseItems,
    { icon: Inbox, title: "全部工单", path: "/admin/tickets" },
    { icon: Users, title: "用户管理", path: "/admin" },
  ],
}

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const items = itemsByRole[getUserRole(currentUser)] ?? baseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
        <div className="px-0.5 group-data-[collapsible=icon]:hidden">
          <WorkspaceSwitcher />
        </div>
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
