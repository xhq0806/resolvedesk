import { Text } from "@react-email/components"
import { Callout, Detail } from "../ui/Callout"
import { Heading } from "../ui/Heading"
import { Layout } from "../ui/Layout"

type TestEmailProps = {
  project_name: string
  email: string
}

export default function TestEmail({
  project_name = "{{ project_name }}",
  email = "{{ email }}",
}: TestEmailProps) {
  return (
    <Layout
      title={`${project_name} - 测试邮件`}
      preview={`${project_name} 邮件投递正常`}
      project_name={project_name}
    >
      <Heading>测试邮件</Heading>
      <Text className="text-[15px] leading-7 text-body">你好：</Text>
      <Text className="text-[15px] leading-7 text-body">
        这是来自 {project_name} 的测试邮件。如果你能看到这封邮件，说明邮件投递配置正确。
      </Text>
      <Callout>
        <Detail label="发送至" value={email} />
      </Callout>
      <Text className="text-sm leading-6 text-muted">
        如果你没有预期收到这封邮件，可以放心忽略。
      </Text>
    </Layout>
  )
}
