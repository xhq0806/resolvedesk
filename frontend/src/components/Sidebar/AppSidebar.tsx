import {
  BookOpen,
  ClipboardClock,
  Home,
  IdCard,
  Inbox,
  ListTodo,
  MessageSquare,
  Settings,
  TicketPlus,
  UserRound,
  Users,
} from "lucide-react"

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
import { openCustomerSupportPanel } from "@/lib/customerSupportEvents"
import type { WorkspaceSummary } from "@/lib/workspaceQueries"
import { useCurrentWorkspace } from "@/lib/workspaceQueries"
import { type Item, Main } from "./Main"
import { User } from "./User"

const commonItems: Item[] = [
  { icon: Home, title: "工作台", path: "/" },
  { icon: Settings, title: "设置", path: "/settings" },
]

const staffItems: Item[] = [
  { icon: MessageSquare, title: "AI 工作台", path: "/ai" },
]

const agentQueueSearch = { page: 1, pageSize: 20, query: "" }

const itemsByWorkspaceRole: Record<WorkspaceSummary["role"], Item[]> = {
  CUSTOMER: [
    { icon: Home, title: "服务台", path: "/" },
    {
      icon: MessageSquare,
      title: "在线咨询",
      action: openCustomerSupportPanel,
    },
    {
      icon: Inbox,
      title: "我的工单",
      path: "/tickets",
      activeSearch: { create: undefined },
    },
    {
      icon: TicketPlus,
      title: "提交工单",
      path: "/tickets",
      search: { page: 1, pageSize: 20, query: "", create: true },
      activeSearch: { create: true },
    },
    { icon: UserRound, title: "我的资料", path: "/settings" },
  ],
  AGENT: [
    { icon: Home, title: "工作台", path: "/" },
    {
      icon: ListTodo,
      title: "客服队列",
      path: "/queue",
      search: { ...agentQueueSearch, view: "unassigned" },
      activeSearch: { view: "unassigned" },
    },
    {
      icon: Inbox,
      title: "我的工单",
      path: "/queue",
      search: { ...agentQueueSearch, view: "mine" },
      activeSearch: { view: "mine" },
    },
    {
      icon: MessageSquare,
      title: "会话",
      path: "/queue",
      search: { ...agentQueueSearch, view: "conversations" },
      activeSearch: { view: "conversations" },
    },
    {
      icon: ClipboardClock,
      title: "工单历史",
      path: "/queue",
      search: { ...agentQueueSearch, view: "history" },
      activeSearch: { view: "history" },
    },
    {
      icon: IdCard,
      title: "客户信息",
      path: "/queue",
      search: { ...agentQueueSearch, view: "customers" },
      activeSearch: { view: "customers" },
    },
    { icon: UserRound, title: "我的资料", path: "/settings" },
  ],
  ADMIN: [
    ...commonItems,
    ...staffItems,
    { icon: BookOpen, title: "知识库", path: "/knowledge" },
    { icon: Inbox, title: "全部工单", path: "/admin/tickets" },
    { icon: Users, title: "用户管理", path: "/admin" },
  ],
  OWNER: [
    ...commonItems,
    ...staffItems,
    { icon: BookOpen, title: "知识库", path: "/knowledge" },
    { icon: Inbox, title: "全部工单", path: "/admin/tickets" },
    { icon: Users, title: "用户管理", path: "/admin" },
  ],
}

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const { role } = useCurrentWorkspace()

  const items = role ? itemsByWorkspaceRole[role] : commonItems

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
