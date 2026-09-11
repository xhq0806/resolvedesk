import { Text } from "@react-email/components"
import { LinkButton } from "../ui/Button"
import { Heading } from "../ui/Heading"
import { Layout } from "../ui/Layout"
import { Link } from "../ui/Link"

type ResetPasswordProps = {
  project_name: string
  username: string
  link: string
  valid_hours: string
}

export default function ResetPassword({
  project_name = "{{ project_name }}",
  username = "{{ username }}",
  link = "{{ link }}",
  valid_hours = "{{ valid_hours }}",
}: ResetPasswordProps) {
  return (
    <Layout
      title={`${project_name} - 找回密码`}
      preview={`重置你的 ${project_name} 密码`}
      project_name={project_name}
    >
      <Heading>重置密码</Heading>
      <Text className="text-[15px] leading-7 text-body">你好，{username}：</Text>
      <Text className="text-[15px] leading-7 text-body">
        我们收到了重置你的 {project_name} 账号密码的请求。请点击下方按钮设置新密码：
      </Text>
      <LinkButton href={link}>重置密码</LinkButton>
      <Text className="text-sm leading-6 text-muted">
        或复制以下链接并粘贴到浏览器中：
        <br />
        <Link href={link}>{link}</Link>
      </Text>
      <Text className="text-sm leading-6 text-muted">
        此链接将在 {valid_hours} 小时后失效。
      </Text>
      <Text className="text-sm leading-6 text-muted">
        如果你没有申请找回密码，可以放心忽略此邮件。
      </Text>
    </Layout>
  )
}
