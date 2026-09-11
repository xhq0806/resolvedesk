import { Link } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import { Button } from "@/components/ui/button"

interface ErrorComponentProps {
  error?: unknown
}

// 为普通 403 提供明确反馈，但不改动当前认证会话。by AI.Coding
const ErrorComponent = ({ error }: ErrorComponentProps) => {
  const isForbidden = isAxiosError(error) && error.response?.status === 403

  return (
    <div
      className="flex min-h-screen items-center justify-center flex-col p-4"
      data-testid="error-component"
    >
      <div className="flex items-center z-10">
        <div className="flex flex-col ml-4 items-center justify-center p-4">
          <span className="text-6xl md:text-8xl font-bold leading-none mb-4">
          {isForbidden ? "403" : "错误"}
          </span>
        <span className="text-2xl font-bold mb-2">出错了！</span>
        </div>
      </div>

      <p className="text-lg text-muted-foreground mb-4 text-center z-10">
        {isForbidden
          ? "你没有权限访问该区域。"
          : "发生了一些问题，请重试。"}
      </p>
      <Link to="/">
        <Button>返回首页</Button>
      </Link>
    </div>
  )
}

export default ErrorComponent
