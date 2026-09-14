// 用户与 AI 头像展示组件，统一图片加载和首字母兜底行为。by AI.Coding

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import { getInitials } from "@/utils"

type UserAvatarProps = {
  name?: string | null
  email?: string | null
  avatarUrl?: string | null
  className?: string
  fallbackClassName?: string
}

export function UserAvatar({
  name,
  email,
  avatarUrl,
  className,
  fallbackClassName,
}: UserAvatarProps) {
  // 用户头像统一优先显示 URL 图片，失败或缺失时显示姓名/邮箱首字母。by AI.Coding
  const label = name?.trim() || email?.trim() || "用户"

  return (
    <Avatar className={cn("size-8", className)}>
      {avatarUrl && <AvatarImage src={avatarUrl} alt={`${label} 的头像`} />}
      <AvatarFallback className={fallbackClassName}>
        {getInitials(label) || "?"}
      </AvatarFallback>
    </Avatar>
  )
}

export function AiAvatar({ className }: { className?: string }) {
  return (
    <Avatar className={cn("size-8", className)}>
      <AvatarFallback className="bg-primary text-xs font-semibold text-primary-foreground">
        {/* AI Agent 使用固定系统头像，明确显示 AI 身份作为兜底。by AI.Coding */}
        <span aria-label="AI Agent">AI</span>
      </AvatarFallback>
    </Avatar>
  )
}
