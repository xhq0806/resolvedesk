import { expect, test } from "@playwright/test"

import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { logInUser, logOutUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

test("Logout clears the session and returns to login", async ({ page }) => {
  await logInUser(page, firstSuperuser, firstSuperuserPassword)
  await logOutUser(page)

  await expect(page).toHaveURL("/login")
  await page.goto("/settings")
  await expect(page).toHaveURL("/login")
})
