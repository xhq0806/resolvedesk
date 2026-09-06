import { redirect } from "@tanstack/react-router"

import type { UserPublic, UserRole } from "@/client"
import { currentUserQueryOptions } from "@/hooks/useAuth"
import {
  clearAuthSession,
  isAuthenticationError,
  queryClient,
} from "./queryClient"

type RequireRolesOptions = {
  allowed: readonly UserRole[]
  redirectTo: "/" | "/login"
}

// 兼容迁移期间的旧字段，所有新导航统一以 role 为准。by AI.Coding
export const getUserRole = (
  user: Partial<Pick<UserPublic, "role" | "is_superuser">> | null | undefined,
): UserRole => user?.role ?? (user?.is_superuser ? "ADMIN" : "CUSTOMER")

// 验证已有 token 后再把用户从登录类页面送回工作台。by AI.Coding
export async function ensureGuest() {
  if (localStorage.getItem("access_token") === null) return

  try {
    await queryClient.fetchQuery({
      ...currentUserQueryOptions(),
      staleTime: 0,
    })
  } catch (error) {
    if (isAuthenticationError(error)) {
      clearAuthSession()
      return
    }
    throw error
  }

  throw redirect({ to: "/" })
}

// 访客路由共享同一套 token 验证，避免仅凭 localStorage 判断登录态。by AI.Coding
export function redirectIfAuthenticated() {
  return ensureGuest
}

// 把当前用户加载、401 清理和角色判断集中到文件路由的 beforeLoad。by AI.Coding
export function requireRoles({ allowed, redirectTo }: RequireRolesOptions) {
  return async () => {
    if (localStorage.getItem("access_token") === null) {
      throw redirect({ to: "/login" })
    }

    let user: UserPublic
    try {
      user = await queryClient.fetchQuery({
        ...currentUserQueryOptions(),
        staleTime: 0,
      })
    } catch (error) {
      if (isAuthenticationError(error)) {
        clearAuthSession()
        throw redirect({ to: "/login" })
      }

      throw error
    }

    if (!allowed.includes(getUserRole(user))) {
      throw redirect({
        to: redirectTo,
        ...(redirectTo === "/" ? { search: { access: "denied" } } : {}),
      })
    }
  }
}
