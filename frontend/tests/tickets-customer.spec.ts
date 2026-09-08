import { expect, test } from "@playwright/test"

import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("Customer can create and view a ticket", async ({ page }) => {
  const email = randomEmail()
  const password = randomPassword()
  const title = `Billing question ${Date.now()}`

  await createUser({ email, password })
  await logInUser(page, email, password)
  await page.goto("/tickets")

  await expect(page.getByRole("heading", { name: "My tickets" })).toBeVisible()
  await page.getByRole("button", { name: "New ticket" }).click()

  const dialog = page.getByRole("dialog")
  await dialog
    .getByPlaceholder("What do you need help with?")
    .fill(title)
  await dialog
    .getByPlaceholder("Describe the issue, impact, and relevant details")
    .fill("Please help me understand this invoice.")
  await dialog.getByRole("combobox").click()
  await page.getByRole("option", { name: "Billing" }).click()
  await dialog.getByRole("button", { name: "Create ticket" }).click()

  await expect(page.getByText("Ticket created successfully")).toBeVisible()
  await expect(page.getByText(title)).toBeVisible()
})
