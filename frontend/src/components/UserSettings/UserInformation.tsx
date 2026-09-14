import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { UsersService, type UserUpdateMe } from "@/client"
import { UserAvatar } from "@/components/Common/UserAvatar"
import { Button } from "@/components/ui/button"
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
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

const formSchema = z.object({
  full_name: z.string().max(30).optional(),
  email: z.email({ message: "请输入有效的邮箱地址" }),
  avatar_url: z
    .string()
    .trim()
    .max(2048, "头像 URL 不能超过 2048 个字符")
    .refine(
      (value) =>
        !value || value.startsWith("http://") || value.startsWith("https://"),
      "头像 URL 必须以 http:// 或 https:// 开头",
    )
    .optional(),
})

type FormData = z.infer<typeof formSchema>

const UserInformation = () => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [editMode, setEditMode] = useState(false)
  const { user: currentUser } = useAuth()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      full_name: currentUser?.full_name ?? undefined,
      email: currentUser?.email,
      avatar_url: currentUser?.avatar_url ?? "",
    },
  })

  const toggleEditMode = () => {
    setEditMode(!editMode)
  }

  const mutation = useMutation({
    mutationFn: (data: UserUpdateMe) =>
      UsersService.updateUserMe({ body: data }),
    onSuccess: () => {
      showSuccessToast("用户信息更新成功")
      toggleEditMode()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries()
    },
  })

  const onSubmit = (data: FormData) => {
    const updateData: UserUpdateMe = {}
    const nextAvatarUrl = data.avatar_url?.trim() || null

    // 只提交发生变化的个人资料字段，头像 URL 为空时表示清除头像。by AI.Coding
    if (data.full_name !== currentUser?.full_name) {
      updateData.full_name = data.full_name
    }
    if (data.email !== currentUser?.email) {
      updateData.email = data.email
    }
    if (nextAvatarUrl !== (currentUser?.avatar_url ?? null)) {
      updateData.avatar_url = nextAvatarUrl
    }

    mutation.mutate(updateData)
  }

  const onCancel = () => {
    form.reset()
    toggleEditMode()
  }

  return (
    <div className="max-w-md">
      <h3 className="text-lg font-semibold py-4">用户信息</h3>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-4"
        >
          <FormField
            control={form.control}
            name="full_name"
            render={({ field }) =>
              editMode ? (
                <FormItem>
                  <FormLabel>姓名</FormLabel>
                  <FormControl>
                    <Input type="text" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              ) : (
                <FormItem>
                  <FormLabel>姓名</FormLabel>
                  <p
                    className={cn(
                      "py-2 truncate max-w-sm",
                      !field.value && "text-muted-foreground",
                    )}
                  >
                    {field.value || "未填写"}
                  </p>
                </FormItem>
              )
            }
          />

          <FormField
            control={form.control}
            name="avatar_url"
            render={({ field }) => {
              const avatarUrl = field.value?.trim() || currentUser?.avatar_url
              return editMode ? (
                <FormItem>
                  <FormLabel>头像 URL</FormLabel>
                  <div className="flex items-center gap-3">
                    <UserAvatar
                      name={form.watch("full_name") || currentUser?.full_name}
                      email={form.watch("email") || currentUser?.email}
                      avatarUrl={avatarUrl}
                      className="size-12"
                    />
                    <FormControl>
                      <Input
                        type="url"
                        placeholder="https://example.com/avatar.png"
                        {...field}
                      />
                    </FormControl>
                  </div>
                  <FormMessage />
                </FormItem>
              ) : (
                <FormItem>
                  <FormLabel>头像</FormLabel>
                  <div className="flex items-center gap-3 py-2">
                    <UserAvatar
                      name={currentUser?.full_name}
                      email={currentUser?.email}
                      avatarUrl={currentUser?.avatar_url}
                      className="size-12"
                    />
                    <p
                      className={cn(
                        "truncate text-sm max-w-xs",
                        !field.value && "text-muted-foreground",
                      )}
                    >
                      {field.value || "未设置"}
                    </p>
                  </div>
                </FormItem>
              )
            }}
          />

          <FormField
            control={form.control}
            name="email"
            render={({ field }) =>
              editMode ? (
                <FormItem>
                  <FormLabel>邮箱</FormLabel>
                  <FormControl>
                    <Input type="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              ) : (
                <FormItem>
                  <FormLabel>邮箱</FormLabel>
                  <p className="py-2 truncate max-w-sm">{field.value}</p>
                </FormItem>
              )
            }
          />

          <div className="flex gap-3">
            {editMode ? (
              <>
                <LoadingButton
                  type="submit"
                  loading={mutation.isPending}
                  disabled={!form.formState.isDirty}
                >
                  保存
                </LoadingButton>
                <Button
                  type="button"
                  variant="outline"
                  onClick={onCancel}
                  disabled={mutation.isPending}
                >
                  取消
                </Button>
              </>
            ) : (
              <Button type="button" onClick={toggleEditMode}>
                编辑
              </Button>
            )}
          </div>
        </form>
      </Form>
    </div>
  )
}

export default UserInformation
