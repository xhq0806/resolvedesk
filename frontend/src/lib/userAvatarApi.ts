// 当前用户头像上传 API 封装，处理本地文件和后端生成的公开头像地址。by AI.Coding

import type { UserPublic } from "@/client"

const apiUrl = () => import.meta.env.VITE_API_URL ?? ""

const authHeaders = (): HeadersInit => ({
  Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
})

const parseErrorMessage = async (response: Response): Promise<string> => {
  // 头像上传不是生成客户端接口，这里复用后端稳定错误结构给出可读提示。by AI.Coding
  const raw = await response.text()
  let message = `请求失败 (${response.status})`
  try {
    const payload = JSON.parse(raw) as {
      message?: unknown
      detail?: unknown
    }
    if (typeof payload.message === "string") {
      message = `${payload.message} (${response.status})`
    } else if (typeof payload.detail === "string") {
      message = `${payload.detail} (${response.status})`
    }
  } catch {
    // 非 JSON 错误响应无法安全提取业务文案，保留 HTTP 状态。by AI.Coding
  }
  return message
}

const requestUser = async (
  path: string,
  init: RequestInit,
): Promise<UserPublic> => {
  // 所有头像写操作都要求当前登录态，浏览器图片读取则不经过这里。by AI.Coding
  const response = await fetch(`${apiUrl()}${path}`, {
    ...init,
    headers: {
      ...authHeaders(),
      ...init.headers,
    },
  })
  if (!response.ok) {
    throw new Error(await parseErrorMessage(response))
  }
  return (await response.json()) as UserPublic
}

export const uploadMyAvatar = async (file: File): Promise<UserPublic> => {
  // 使用 multipart/form-data 上传真实本地图片，Content-Type 交给浏览器生成边界。by AI.Coding
  const formData = new FormData()
  formData.append("file", file)
  return requestUser("/api/v1/users/me/avatar", {
    method: "POST",
    body: formData,
  })
}

export const deleteMyAvatar = async (): Promise<UserPublic> => {
  // 清除当前登录用户头像并返回更新后的用户资料。by AI.Coding
  return requestUser("/api/v1/users/me/avatar", {
    method: "DELETE",
  })
}

export const resolveAvatarUrl = (avatarUrl?: string | null): string | null => {
  // 后端返回相对 API 地址时，前端开发服务器需要补齐 VITE_API_URL。by AI.Coding
  if (!avatarUrl) return null
  if (avatarUrl.startsWith("/api/")) {
    return `${apiUrl()}${avatarUrl}`
  }
  return avatarUrl
}
