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
            {isForbidden ? "403" : "Error"}
          </span>
          <span className="text-2xl font-bold mb-2">Oops!</span>
        </div>
      </div>

      <p className="text-lg text-muted-foreground mb-4 text-center z-10">
        {isForbidden
          ? "You do not have permission to access this area."
          : "Something went wrong. Please try again."}
      </p>
      <Link to="/">
        <Button>Go Home</Button>
      </Link>
    </div>
  )
}

export default ErrorComponent
