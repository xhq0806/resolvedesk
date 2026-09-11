import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { isAxiosError } from "axios"
import { Pencil } from "lucide-react"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { UserPublic, UserRole } from "@/client"
import { UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { invalidateUserQueries } from "@/lib/userQueries"
import { handleError } from "@/utils"

const formSchema = z
  .object({
    email: z.email({ message: "请输入有效的邮箱地址" }),
    full_name: z.string().optional(),
    password: z
      .string()
      .min(8, { message: "密码至少需要 8 个字符" })
      .optional()
      .or(z.literal("")),
    confirm_password: z.string().optional(),
    role: z.enum(["CUSTOMER", "AGENT", "ADMIN"]),
    is_active: z.boolean(),
  })
  .refine((data) => !data.password || data.password === data.confirm_password, {
    message: "两次输入的密码不一致",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

interface EditUserProps {
  user: UserPublic
  onSuccess: () => void
}

const roleOptions: Array<{ value: UserRole; label: string }> = [
  { value: "CUSTOMER", label: "客户" },
  { value: "AGENT", label: "客服" },
  { value: "ADMIN", label: "管理员" },
]

const EditUser = ({ user, onSuccess }: EditUserProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  // 当前用户用于判断是否需要刷新自身缓存，避免编辑后页面仍显示旧状态。by AI.Coding
  const { user: currentUser } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: user.email,
      full_name: user.full_name ?? undefined,
      role: user.role ?? "CUSTOMER",
      is_active: user.is_active ?? true,
    },
  })

  useEffect(() => {
    if (!isOpen) return
    form.reset({
      email: user.email,
      full_name: user.full_name ?? undefined,
      role: user.role ?? "CUSTOMER",
      is_active: user.is_active ?? true,
      password: "",
      confirm_password: "",
    })
  }, [form, isOpen, user])

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      UsersService.updateUser({ path: { user_id: user.id }, body: data }),
    onSuccess: async () => {
      await invalidateUserQueries(queryClient, {
        includeCurrentUser: user.id === currentUser?.id,
      })
      showSuccessToast("用户更新成功")
      setIsOpen(false)
      onSuccess()
    },
    onError: (error: Error) => {
      handleError.call(showErrorToast, error)
      // 最后一个活跃 Admin 的限制由结构化 code 返回，这里直接映射到表单错误。by AI.Coding
      const errorCode = isAxiosError(error)
        ? (error.response?.data as { code?: string } | undefined)?.code
        : undefined
      if (errorCode === "LAST_ACTIVE_ADMIN") {
        form.setError("role", {
          message: "系统至少需要一名启用中的管理员。",
        })
        form.setError("is_active", {
          message: "系统至少需要一名启用中的管理员。",
        })
      }
    },
    onSettled: () => {
      void invalidateUserQueries(queryClient)
    },
  })

  const onSubmit = (data: FormData) => {
    const { confirm_password: _, ...submitData } = data
    if (!submitData.password) {
      delete submitData.password
    }
    mutation.mutate(submitData)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem onSelect={(e) => e.preventDefault()} onClick={() => setIsOpen(true)}>
        <Pencil />
        编辑用户
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>编辑用户</DialogTitle>
              <DialogDescription>请在下方更新用户信息。</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>邮箱</FormLabel>
                    <FormControl>
                    <Input placeholder="请输入邮箱" type="email" {...field} required />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="full_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>姓名</FormLabel>
                    <FormControl>
                    <Input placeholder="请输入姓名" type="text" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="role"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>角色</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="请选择角色" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {roleOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>设置密码</FormLabel>
                    <FormControl>
                    <Input placeholder="请输入密码" type="password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="confirm_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>确认密码</FormLabel>
                    <FormControl>
                    <Input placeholder="请再次输入密码" type="password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="is_active"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  <FormLabel className="font-normal">启用账号</FormLabel>
                  </FormItem>
                )}
              />
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                取消
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
              保存
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default EditUser
