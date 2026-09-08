import { AxiosError } from "axios"

function extractErrorMessage(err: Error): string {
  if (err instanceof AxiosError) {
    // 鍏煎棰嗗煙閿欒鐨勭粨鏋勫寲 message 鍜岀幇鏈夌殑 detail 鍝嶅簲銆俠y AI.Coding
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
  return "Something went wrong."
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
