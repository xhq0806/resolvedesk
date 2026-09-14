import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import type { LucideIcon } from "lucide-react"
import type { MouseEvent } from "react"

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export type Item = {
  icon: LucideIcon
  title: string
  path?: string
  search?: Record<string, string | number | boolean | undefined>
  activeSearch?: Record<string, string | number | boolean | undefined>
  action?: () => void
}

interface MainProps {
  items: Item[]
}

export function Main({ items }: MainProps) {
  const { isMobile, setOpenMobile } = useSidebar()
  const router = useRouterState()
  const currentPath = router.location.pathname
  const currentSearch = router.location.search as Record<string, unknown>

  const handleMenuClick = () => {
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  const handleActionClick = (
    event: MouseEvent<HTMLButtonElement>,
    action: () => void,
  ) => {
    // 动作型菜单用于打开在线咨询等浮层，仍复用移动端收起逻辑。by AI.Coding
    event.preventDefault()
    action()
    handleMenuClick()
  }

  return (
    <SidebarGroup>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => {
            // 进入详情页时仍沿用父级导航高亮，带筛选入口只比较声明的关键 search。by AI.Coding
            const isPathActive = item.path
              ? currentPath === item.path ||
                (item.path !== "/" && currentPath.startsWith(`${item.path}/`))
              : false
            const activeSearch = item.activeSearch ?? {}
            const isSearchActive = Object.entries(activeSearch).every(
              ([key, value]) => currentSearch[key] === value,
            )
            const isActive = isPathActive && isSearchActive

            if (item.action) {
              const action = item.action
              return (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton tooltip={item.title} asChild>
                    <button
                      type="button"
                      onClick={(event) => handleActionClick(event, action)}
                    >
                      <item.icon />
                      <span>{item.title}</span>
                    </button>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )
            }

            if (!item.path) return null

            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  tooltip={item.title}
                  isActive={isActive}
                  asChild
                >
                  <RouterLink
                    to={item.path}
                    search={item.search}
                    onClick={handleMenuClick}
                  >
                    <item.icon />
                    <span>{item.title}</span>
                  </RouterLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
