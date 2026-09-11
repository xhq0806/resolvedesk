import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { MessageSquare, Send } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  type TicketMessageType,
  TicketsService,
  type UserRole,
} from "@/client"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { invalidateTicketQueries } from "@/lib/ticketQueries"
import { handleError } from "@/utils"

const formSchema = z.object({
  messageType: z.enum(["PUBLIC_REPLY", "INTERNAL_NOTE"]),
  content: z
    .string()
    .trim()
    .min(1, "请输入消息")
    .max(10000, "消息不能超过 10,000 个字符"),
})

type FormData = z.infer<typeof formSchema>

// 根据角色复用公开回复和内部备注的提交表单，权限判断仍由后端执行。by AI.Coding
export function TicketReplyForm({
  ticketId,
  role,
  allowInternal,
}: {
  ticketId: string
  role: UserRole
  allowInternal: boolean
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: {
      messageType: allowInternal ? "PUBLIC_REPLY" : "PUBLIC_REPLY",
      content: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) => {
      if (role === "CUSTOMER") {
        return TicketsService.addCustomerReply({
          path: { ticket_id: ticketId },
          body: { content: data.content },
        })
      }

      return TicketsService.addStaffMessage({
        path: { ticket_id: ticketId },
        body: {
          message_type: data.messageType as TicketMessageType,
          content: data.content,
        },
      })
    },
    onSuccess: (_response, data) => {
      showSuccessToast(
        data.messageType === "INTERNAL_NOTE"
      ? "内部备注已添加。"
      : "回复发送成功。",
      )
      form.reset({ messageType: data.messageType, content: "" })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () =>
      invalidateTicketQueries(queryClient, { ticketId }),
  })

  const messageType = form.watch("messageType")
  const isInternal = messageType === "INTERNAL_NOTE"

  return (
    <div className="rounded-lg border bg-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
        <h2 className="font-semibold">
      {isInternal ? "添加内部备注" : "撰写回复"}
        </h2>
      </div>
      {allowInternal && (
        <Tabs
          value={messageType}
          onValueChange={(value) =>
            form.setValue("messageType", value as TicketMessageType)
          }
          className="mb-4"
        >
          <TabsList>
          <TabsTrigger value="PUBLIC_REPLY">公开回复</TabsTrigger>
          <TabsTrigger value="INTERNAL_NOTE">内部备注</TabsTrigger>
          </TabsList>
        </Tabs>
      )}
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
          className="grid gap-4"
        >
          <FormField
            control={form.control}
            name="content"
            render={({ field }) => (
              <FormItem>
              <FormLabel>{isInternal ? "备注" : "回复"}</FormLabel>
                <FormControl>
                  <Textarea
                    placeholder={
                      isInternal
              ? "为客服团队补充上下文"
              : "向提单人分享最新进展"
                    }
                    className="min-h-28 resize-y"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="flex justify-end">
            <LoadingButton type="submit" loading={mutation.isPending}>
              <Send className="h-4 w-4" />
              {isInternal ? "添加备注" : "发送回复"}
            </LoadingButton>
          </div>
        </form>
      </Form>
    </div>
  )
}
