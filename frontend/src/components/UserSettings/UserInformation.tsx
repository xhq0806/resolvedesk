import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
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
import useAuth, { userKeys } from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { deleteMyAvatar, uploadMyAvatar } from "@/lib/userAvatarApi"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

const formSchema = z.object({
  full_name: z.string().max(30).optional(),
  email: z.email({ message: "请输入有效的邮箱地址" }),
})

type FormData = z.infer<typeof formSchema>

const UserInformation = () => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [editMode, setEditMode] = useState(false)
  const [selectedAvatarFile, setSelectedAvatarFile] = useState<File | null>(null)
  const [avatarPreviewUrl, setAvatarPreviewUrl] = useState<string | null>(null)
  const { user: currentUser } = useAuth()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      full_name: currentUser?.full_name ?? undefined,
      email: currentUser?.email,
    },
  })

  useEffect(() => {
    // 为本地待上传图片创建临时预览，并在替换或卸载时释放浏览器资源。by AI.Coding
    if (!selectedAvatarFile) {
      setAvatarPreviewUrl(null)
      return
    }
    const nextPreviewUrl = URL.createObjectURL(selectedAvatarFile)
    setAvatarPreviewUrl(nextPreviewUrl)
    return () => URL.revokeObjectURL(nextPreviewUrl)
  }, [selectedAvatarFile])

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

  const uploadAvatarMutation = useMutation({
    mutationFn: uploadMyAvatar,
    onSuccess: (updatedUser) => {
      // 头像展示位都依赖 currentUser 缓存，上传响应要立即写回，避免继续显示旧首字母。by AI.Coding
      queryClient.setQueryData(userKeys.current, updatedUser)
      showSuccessToast("头像上传成功")
      setSelectedAvatarFile(null)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries()
    },
  })

  const deleteAvatarMutation = useMutation({
    mutationFn: deleteMyAvatar,
    onSuccess: (updatedUser) => {
      // 清除头像后同步当前用户缓存，确保侧边栏和在线咨询立刻回到首字母兜底。by AI.Coding
      queryClient.setQueryData(userKeys.current, updatedUser)
      showSuccessToast("头像已清除")
      setSelectedAvatarFile(null)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries()
    },
  })

  const onSubmit = (data: FormData) => {
    const updateData: UserUpdateMe = {}

    // 只提交发生变化的个人资料字段，头像由专用本地上传接口处理。by AI.Coding
    if (data.full_name !== currentUser?.full_name) {
      updateData.full_name = data.full_name
    }
    if (data.email !== currentUser?.email) {
      updateData.email = data.email
    }

    mutation.mutate(updateData)
  }

  const onCancel = () => {
    form.reset()
    setSelectedAvatarFile(null)
    toggleEditMode()
  }

  const onUploadAvatar = () => {
    // 用户必须显式选择本地图片后才触发上传，避免空请求进入后端。by AI.Coding
    if (selectedAvatarFile) {
      uploadAvatarMutation.mutate(selectedAvatarFile)
    }
  }

  const onDeleteAvatar = () => {
    deleteAvatarMutation.mutate()
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

          <FormItem>
            <FormLabel>头像</FormLabel>
            {editMode ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <UserAvatar
                    name={form.watch("full_name") || currentUser?.full_name}
                    email={form.watch("email") || currentUser?.email}
                    avatarUrl={avatarPreviewUrl || currentUser?.avatar_url}
                    className="size-12"
                  />
                  <div className="flex-1">
                    <Input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      onChange={(event) => {
                        // 只保留最新选择的一个本地头像文件。by AI.Coding
                        setSelectedAvatarFile(event.target.files?.[0] ?? null)
                      }}
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      支持 PNG、JPG、WebP，最大 2 MB
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <LoadingButton
                    type="button"
                    variant="secondary"
                    loading={uploadAvatarMutation.isPending}
                    disabled={!selectedAvatarFile}
                    onClick={onUploadAvatar}
                  >
                    上传头像
                  </LoadingButton>
                  <LoadingButton
                    type="button"
                    variant="outline"
                    loading={deleteAvatarMutation.isPending}
                    disabled={!currentUser?.avatar_url}
                    onClick={onDeleteAvatar}
                  >
                    清除头像
                  </LoadingButton>
                </div>
              </div>
            ) : (
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
                    !currentUser?.avatar_url && "text-muted-foreground",
                  )}
                >
                  {currentUser?.avatar_url ? "已设置" : "未设置"}
                </p>
              </div>
            )}
          </FormItem>

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
