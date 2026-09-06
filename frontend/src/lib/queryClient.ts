// 前端认证查询客户端与会话清理策略。by AI.Coding
import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query"
import { isAxiosError } from "axios"

let queryClient: QueryClient

// 清除当前会话及全部服务端缓存，避免账号切换时短暂暴露旧数据。by AI.Coding
export const clearAuthSession = () => {
  localStorage.removeItem("access_token")
  queryClient.clear()
}

// 兼容后端当前对无效 JWT 返回 403 的实现，同时区分普通角色越权。by AI.Coding
export const isAuthenticationError = (error: unknown) => {
  if (!isAxiosError(error)) return false

  const status = error.response?.status
  const detail = (error.response?.data as { detail?: unknown } | undefined)
    ?.detail
  if (status === 401) return true

  return status === 403 && detail === "Could not validate credentials"
}

// 仅凭证失效时清理会话；普通 403 交给角色守卫或页面展示权限错误。by AI.Coding
const handleApiError = (error: Error) => {
  if (!isAuthenticationError(error)) return

  clearAuthSession()
  if (window.location.pathname !== "/login") {
    window.location.assign("/login")
  }
}

queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleApiError }),
  mutationCache: new MutationCache({ onError: handleApiError }),
})

export { queryClient }
