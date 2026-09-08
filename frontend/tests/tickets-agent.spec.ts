import { expect, test } from "@playwright/test"

import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser, logOutUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("Agent can open the service queue and its role-specific views", async ({
  page,
}) => {
  const email = randomEmail()
  const password = randomPassword()

  await logInUser(page, firstSuperuser, firstSuperuserPassword)
  await page.goto("/admin")
  await page.getByRole("button", { name: /Add user/i }).click()

  const dialog = page.getByRole("dialog")
  await dialog.getByPlaceholder("Email").fill(email)
  await dialog.getByPlaceholder("Password").first().fill(password)
  await dialog.getByPlaceholder("Password").last().fill(password)
  await dialog.getByRole("combobox").click()
  await page.getByRole("option", { name: "Agent" }).click()
  await dialog.getByRole("button", { name: "Save" }).click()

  await expect(page.getByText("User created successfully")).toBeVisible()
  await logOutUser(page)
  await logInUser(page, email, password)
  await page.goto("/queue")

  await expect(page.getByRole("heading", { name: "Service queue" })).toBeVisible()
  await expect(
    page.getByRole("tab", { name: /Unassigned queue/i }),
  ).toBeVisible()
  await expect(page.getByRole("tab", { name: /My tickets/i })).toBeVisible()
  await expect(
    page.getByRole("tab", { name: /Waiting for customer/i }),
  ).toBeVisible()
})
