import { expect, test } from "@playwright/test"

import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test("Admin users page is accessible", async ({ page }) => {
  await page.goto("/admin")
  await expect(page.getByRole("heading", { name: "用户管理" })).toBeVisible()
  await expect(
    page.getByText("管理用户账号和权限"),
  ).toBeVisible()
  await expect(page.getByRole("button", { name: "添加用户" })).toBeVisible()
})

test.describe("Admin user management", () => {
  test("creates a customer with the default role", async ({ page }) => {
    await page.goto("/admin")

    const email = randomEmail()
    const password = randomPassword()
    const dialog = page.getByRole("dialog")

    await page.getByRole("button", { name: "添加用户" }).click()
    await dialog.getByPlaceholder("请输入邮箱").fill(email)
    await dialog.getByPlaceholder("请输入姓名").fill("Test Customer")
    await dialog.getByPlaceholder("请输入密码").first().fill(password)
    await dialog.getByPlaceholder("请再次输入密码").fill(password)
    await dialog.getByRole("button", { name: "保存" }).click()

    await expect(page.getByText("用户创建成功")).toBeVisible()
    await expect(dialog).not.toBeVisible()
    await expect(page.getByRole("row").filter({ hasText: email })).toBeVisible()
  })

  test("creates an agent with an explicit role", async ({ page }) => {
    await page.goto("/admin")

    const email = randomEmail()
    const password = randomPassword()
    const dialog = page.getByRole("dialog")

    await page.getByRole("button", { name: "添加用户" }).click()
    await dialog.getByPlaceholder("请输入邮箱").fill(email)
    await dialog.getByPlaceholder("请输入密码").first().fill(password)
    await dialog.getByPlaceholder("请再次输入密码").fill(password)
    await dialog.getByRole("combobox").click()
    await page.getByRole("option", { name: "客服" }).click()
    await dialog.getByRole("button", { name: "保存" }).click()

    await expect(page.getByText("用户创建成功")).toBeVisible()
    await expect(
      page.getByRole("row").filter({ hasText: email }).getByText("客服"),
    ).toBeVisible()
  })

  test("edits a user's role and active state", async ({ page }) => {
    await page.goto("/admin")

    const email = randomEmail()
    const password = randomPassword()
    const dialog = page.getByRole("dialog")

    await page.getByRole("button", { name: "添加用户" }).click()
    await dialog.getByPlaceholder("请输入邮箱").fill(email)
    await dialog.getByPlaceholder("请输入密码").first().fill(password)
    await dialog.getByPlaceholder("请再次输入密码").fill(password)
    await dialog.getByRole("button", { name: "保存" }).click()
    await expect(page.getByText("用户创建成功")).toBeVisible()

    const userRow = page.getByRole("row").filter({ hasText: email })
    await userRow.getByRole("button").click()
    await page.getByRole("menuitem", { name: /编辑用户/i }).click()

    const editDialog = page.getByRole("dialog")
    await editDialog.getByRole("combobox").click()
    await page.getByRole("option", { name: "客服" }).click()
    await editDialog.getByRole("checkbox").uncheck()
    await editDialog.getByRole("button", { name: "保存" }).click()

    await expect(page.getByText("用户更新成功")).toBeVisible()
    await expect(userRow.getByText("客服")).toBeVisible()
    await expect(userRow.getByText("停用")).toBeVisible()
  })

  test("shows form validation errors", async ({ page }) => {
    await page.goto("/admin")
    const dialog = page.getByRole("dialog")

    await page.getByRole("button", { name: "添加用户" }).click()
    await dialog.getByPlaceholder("请输入邮箱").fill("invalid-email")
    await dialog.getByPlaceholder("请输入邮箱").blur()
    await expect(dialog.getByText("请输入有效的邮箱地址")).toBeVisible()

    await dialog.getByPlaceholder("请输入密码").first().fill("short")
    await dialog.getByPlaceholder("请再次输入密码").fill("different12345")
    await dialog.getByRole("button", { name: "保存" }).click()
    await expect(
      dialog.getByText("密码至少需要 8 个字符"),
    ).toBeVisible()
    await expect(dialog.getByText("两次输入的密码不一致")).toBeVisible()
  })
})

test.describe("Admin page access control", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Customer cannot access admin pages", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()

    await createUser({ email, password })
    await logInUser(page, email, password)
    await page.goto("/admin")

    await expect(page.getByRole("heading", { name: "用户管理" })).not.toBeVisible()
    await expect(page).not.toHaveURL(/\/admin/)
  })

  test("Admin can access users and tickets pages", async ({ page }) => {
    await logInUser(page, firstSuperuser, firstSuperuserPassword)

    await page.goto("/admin")
    await expect(page.getByRole("heading", { name: "用户管理" })).toBeVisible()

    await page.goto("/admin/tickets")
    await expect(page.getByRole("heading", { name: "全部工单" })).toBeVisible()
  })
})
