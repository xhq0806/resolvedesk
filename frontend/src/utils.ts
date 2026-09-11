import { AxiosError } from "axios"

function extractErrorMessage(err: Error): string {
  if (err instanceof AxiosError) {
    // 兼容领域错误的结构化 message 和现有的 detail 响应。by AI.Coding
    const payload = err.response?.data as {
      message?: unknown
      detail?: unknown
    } | undefined
    if (typeof payload?.message === "string") {
      return payload.message
    }
    const errDetail = payload?.detail
    if (Array.isArray(errDetail) && errDetail.length > 0) {
      return errDetail[0].msg
    }
    if (typeof errDetail === "string") {
      return errDetail
    }
    return err.message
  }
  return "发生了一些问题，请重试。"
}

export const handleError = function (this: (msg: string) => void, err: Error) {
  const errorMessage = extractErrorMessage(err)
  this(errorMessage)
}

export const getInitials = (name: string): string => {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
}
