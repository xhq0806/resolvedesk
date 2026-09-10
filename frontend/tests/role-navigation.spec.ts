import { expect, test } from "@playwright/test"

import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser, logOutUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("Customer workspace shows customer navigation and blocks agent pages", async ({
  page,
}) => {
  const email = randomEmail()
  const password = randomPassword()

  await createUser({ email, password })
  await logInUser(page, email, password)

  await expect(
    page.getByRole("link", { name: "My tickets", exact: true }),
  ).toBeVisible()
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible()

  await page.goto("/queue")
  await expect(page).toHaveURL(/\/\?access=denied/)
  await expect(
    page.getByText("You do not have permission to access that area."),
  ).toBeVisible()
})

test("Agent workspace shows queue navigation and blocks customer pages", async ({
  page,
}) => {
  const agentEmail = randomEmail()
  const agentPassword = randomPassword()

  await logInUser(page, firstSuperuser, firstSuperuserPassword)
  await page.goto("/admin")
  await page.getByRole("button", { name: /Add user/i }).click()

  const dialog = page.getByRole("dialog")
  await dialog.getByPlaceholder("Email").fill(agentEmail)
  await dialog.getByPlaceholder("Password").first().fill(agentPassword)
  await dialog.getByPlaceholder("Password").last().fill(agentPassword)
  await dialog.getByRole("combobox").click()
  await page.getByRole("option", { name: "Agent" }).click()
  await dialog.getByRole("button", { name: "Save" }).click()

  await expect(page.getByText("User created successfully")).toBeVisible()
  await logOutUser(page)
  await logInUser(page, agentEmail, agentPassword)

  await expect(
    page.getByRole("link", { name: "Service queue", exact: true }),
  ).toBeVisible()
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible()

  await page.goto("/tickets")
  await expect(page).toHaveURL(/\/\?access=denied/)
})

test("Admin workspace shows admin navigation", async ({ page }) => {
  await logInUser(page, firstSuperuser, firstSuperuserPassword)

  await expect(
    page.getByRole("link", { name: "Tickets", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Users", exact: true }),
  ).toBeVisible()
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible()

  await page.goto("/admin/tickets")
  await expect(page.getByRole("heading", { name: "All tickets" })).toBeVisible()
})
