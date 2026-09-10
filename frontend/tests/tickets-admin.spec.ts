import { expect, test } from "@playwright/test"

test("Admin can open the global ticket management page", async ({ page }) => {
  await page.goto("/admin/tickets")

  await expect(page.getByRole("heading", { name: "All tickets" })).toBeVisible()
  await expect(
    page.getByPlaceholder("Search by title or ticket number"),
  ).toBeVisible()
  await expect(page.getByLabel("Assignee")).toBeVisible()
})
