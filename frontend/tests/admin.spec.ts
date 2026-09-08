import { expect, test } from "@playwright/test"

import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test("Admin users page is accessible", async ({ page }) => {
  await page.goto("/admin")
  await expect(page.getByRole("heading", { name: "Users" })).toBeVisible()
  await expect(
    page.getByText("Manage user accounts and permissions"),
  ).toBeVisible()
  await expect(page.getByRole("button", { name: /Add user/i })).toBeVisible()
})

test.describe("Admin user management", () => {
  test("creates a customer with the default role", async ({ page }) => {
    await page.goto("/admin")

    const email = randomEmail()
    const password = randomPassword()
    const dialog = page.getByRole("dialog")

    await page.getByRole("button", { name: /Add user/i }).click()
    await dialog.getByPlaceholder("Email").fill(email)
    await dialog.getByPlaceholder("Full name").fill("Test Customer")
    await dialog.getByPlaceholder("Password").first().fill(password)
    await dialog.getByPlaceholder("Password").last().fill(password)
    await dialog.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User created successfully")).toBeVisible()
    await expect(dialog).not.toBeVisible()
    await expect(page.getByRole("row").filter({ hasText: email })).toBeVisible()
  })

  test("creates an agent with an explicit role", async ({ page }) => {
    await page.goto("/admin")

    const email = randomEmail()
    const password = randomPassword()
    const dialog = page.getByRole("dialog")

    await page.getByRole("button", { name: /Add user/i }).click()
    await dialog.getByPlaceholder("Email").fill(email)
    await dialog.getByPlaceholder("Password").first().fill(password)
    await dialog.getByPlaceholder("Password").last().fill(password)
    await dialog.getByRole("combobox").click()
    await page.getByRole("option", { name: "Agent" }).click()
    await dialog.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User created successfully")).toBeVisible()
    await expect(
      page.getByRole("row").filter({ hasText: email }).getByText("Agent"),
    ).toBeVisible()
  })

  test("edits a user's role and active state", async ({ page }) => {
    await page.goto("/admin")

    const email = randomEmail()
    const password = randomPassword()
    const dialog = page.getByRole("dialog")

    await page.getByRole("button", { name: /Add user/i }).click()
    await dialog.getByPlaceholder("Email").fill(email)
    await dialog.getByPlaceholder("Password").first().fill(password)
    await dialog.getByPlaceholder("Password").last().fill(password)
    await dialog.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("User created successfully")).toBeVisible()

    const userRow = page.getByRole("row").filter({ hasText: email })
    await userRow.getByRole("button").click()
    await page.getByRole("menuitem", { name: /Edit user/i }).click()

    const editDialog = page.getByRole("dialog")
    await editDialog.getByRole("combobox").click()
    await page.getByRole("option", { name: "Agent" }).click()
    await editDialog.getByRole("checkbox").uncheck()
    await editDialog.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User updated successfully")).toBeVisible()
    await expect(userRow.getByText("Agent")).toBeVisible()
    await expect(userRow.getByText("Inactive")).toBeVisible()
  })

  test("shows form validation errors", async ({ page }) => {
    await page.goto("/admin")
    const dialog = page.getByRole("dialog")

    await page.getByRole("button", { name: /Add user/i }).click()
    await dialog.getByPlaceholder("Email").fill("invalid-email")
    await dialog.getByPlaceholder("Email").blur()
    await expect(dialog.getByText("Invalid email address")).toBeVisible()

    await dialog.getByPlaceholder("Password").first().fill("short")
    await dialog.getByPlaceholder("Password").last().fill("different12345")
    await dialog.getByRole("button", { name: "Save" }).click()
    await expect(
      dialog.getByText("Password must be at least 8 characters"),
    ).toBeVisible()
    await expect(dialog.getByText("The passwords don't match")).toBeVisible()
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

    await expect(page.getByRole("heading", { name: "Users" })).not.toBeVisible()
    await expect(page).not.toHaveURL(/\/admin/)
  })

  test("Admin can access users and tickets pages", async ({ page }) => {
    await logInUser(page, firstSuperuser, firstSuperuserPassword)

    await page.goto("/admin")
    await expect(page.getByRole("heading", { name: "Users" })).toBeVisible()

    await page.goto("/admin/tickets")
    await expect(page.getByRole("heading", { name: "All tickets" })).toBeVisible()
  })
})
