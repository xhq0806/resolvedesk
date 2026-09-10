import { Link } from "@tanstack/react-router"
import { Headset } from "lucide-react"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

// ResolveDesk 使用轻量的文字与耳机标识，避免继续依赖上游模板 Logo。by AI.Coding
export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  // 根据侧栏状态切换完整品牌和紧凑图标，保持布局宽度稳定。by AI.Coding
  const content =
    variant === "responsive" ? (
      <>
        <span
          className={cn(
            "inline-flex items-center gap-2",
            className,
            "group-data-[collapsible=icon]:hidden",
          )}
        >
          <Headset className="size-5 shrink-0" aria-hidden="true" />
          <span className="text-base font-semibold tracking-tight">
            ResolveDesk
          </span>
        </span>
        <Headset
          className={cn(
            "hidden size-5 group-data-[collapsible=icon]:block",
            className,
          )}
          aria-label="ResolveDesk"
        />
      </>
    ) : variant === "icon" ? (
      <Headset className={cn("size-5", className)} aria-label="ResolveDesk" />
    ) : (
      <span className={cn("inline-flex items-center gap-3", className)}>
        <Headset className="size-7 shrink-0" aria-hidden="true" />
        <span className="text-2xl font-semibold tracking-tight">
          ResolveDesk
        </span>
      </span>
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
