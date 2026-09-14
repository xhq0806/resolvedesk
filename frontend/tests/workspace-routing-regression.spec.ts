import { expect, test } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config"

test.use({ storageState: { cookies: [], origins: [] } })

test("管理员进入工作台和全部工单不会因旧 Workspace ID 报错", async ({ page }) => {
  // 使用中文界面真实登录，覆盖工作台统计和管理员工单列表的租户请求头。by AI.Coding
  await page.goto("/login")
  await page.getByTestId("email-input").fill(firstSuperuser)
  await page.getByTestId("password-input").fill(firstSuperuserPassword)
  await page.getByRole("button", { name: "登录" }).click()
  await page.waitForURL("/")
  await expect(page.getByRole("heading", { name: /工作台/ })).toBeVisible()

  await page.goto("/admin/tickets")
  await expect(page.getByRole("heading", { name: "全部工单" })).toBeVisible()
})
