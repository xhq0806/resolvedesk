import { expect, test } from "@playwright/test"

import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { logInUser } from "./utils/user"

test("Admin can open the global ticket management page", async ({ page }) => {
  await logInUser(page, firstSuperuser, firstSuperuserPassword)
  await page.goto("/admin/tickets")

  await expect(page.getByRole("heading", { name: "All tickets" })).toBeVisible()
  await expect(
    page.getByPlaceholder("Search by title or ticket number"),
  ).toBeVisible()
  await expect(page.getByLabel("Assignee")).toBeVisible()
})
