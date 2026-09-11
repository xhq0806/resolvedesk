import { Text } from "@react-email/components"
import { LinkButton } from "../ui/Button"
import { Callout, Detail } from "../ui/Callout"
import { Heading } from "../ui/Heading"
import { Layout } from "../ui/Layout"
import { Link } from "../ui/Link"

type NewAccountProps = {
  project_name: string
  username: string
  password: string
  link: string
}

export default function NewAccount({
  project_name = "{{ project_name }}",
  username = "{{ username }}",
  password = "{{ password }}",
  link = "{{ link }}",
}: NewAccountProps) {
  return (
    <Layout
      title={`${project_name} - 新账号`}
      preview={`${project_name} 账号已准备就绪`}
      project_name={project_name}
    >
      <Heading>欢迎使用 {project_name}！</Heading>
      <Text className="text-[15px] leading-7 text-body">你好：</Text>
      <Text className="text-[15px] leading-7 text-body">
        你的账号已创建成功，可以开始使用。以下是你的登录信息：
      </Text>
      <Callout>
        <Detail label="用户名" value={username} />
        <Detail label="密码" value={password} />
      </Callout>
      <Text className="text-[15px] leading-7 text-body">
        请登录工作台开始使用：
      </Text>
      <LinkButton href={link}>进入工作台</LinkButton>
      <Text className="text-sm leading-6 text-muted">
        或复制以下链接并粘贴到浏览器中：
        <br />
        <Link href={link}>{link}</Link>
      </Text>
      <Text className="text-sm leading-6 text-muted">
        出于安全考虑，请在首次登录后修改密码。
      </Text>
    </Layout>
  )
}
