// 验证 ResolveDesk 三角色业务闭环与关键安全不变量。by AI.Coding
import { expect, type Page, test } from "@playwright/test"

import {
  apiBaseUrl,
  authHeaders,
  closeRoleContexts,
  createRoleContexts,
} from "./utils/roleContexts.ts"

const selectOption = async (page: Page, label: string, option: string) => {
  await page.getByLabel(label, { exact: true }).click()
  await page.getByRole("option", { name: option, exact: true }).click()
}

test.describe.serial("Three-role ticket workflow", () => {
    test("completes the lifecycle and enforces security boundaries", async ({
      browser,
      request,
    }) => {
      test.setTimeout(180_000)
      const roles = await createRoleContexts(request, browser)
      for (const role of Object.values(roles)) {
        role.page.setDefaultTimeout(15_000)
      }
      const title = `E2E lifecycle ${Date.now()}`
      const adminOnlyNote = `admin-only-${Date.now()}`
      const agentReply = `public-agent-reply-${Date.now()}`
      const agentOnlyNote = `agent-only-${Date.now()}`
      let ticketId = ""

      try {
        // Customer 从自己的工作台创建工单，并进入详情页。
        await roles.customer.page.goto("/tickets")
        await expect(
          roles.customer.page.getByRole("link", {
            name: "My tickets",
            exact: true,
          }),
        ).toBeVisible()
        await roles.customer.page
          .getByRole("button", { name: "New ticket" })
          .click()
        const createDialog = roles.customer.page.getByRole("dialog")
        await createDialog
          .getByPlaceholder("What do you need help with?")
          .fill(title)
        await createDialog
          .getByPlaceholder("Describe the issue, impact, and relevant details")
          .fill(
            "A reproducible billing issue for the release acceptance workflow.",
          )
        await createDialog.getByRole("combobox").click()
        await roles.customer.page
          .getByRole("option", { name: "Billing", exact: true })
          .click()
        await createDialog
          .getByRole("button", { name: "Create ticket" })
          .click()
        await expect(
          roles.customer.page.getByText("Ticket created successfully"),
        ).toBeVisible()
        const ticketLink = roles.customer.page.getByRole("link", {
          name: title,
          exact: true,
        })
        await expect(ticketLink).toBeVisible()
        const ticketHref = await ticketLink.getAttribute("href")
        ticketId = ticketHref?.match(/\/tickets\/([^?]+)/)?.[1] ?? ""
        expect(ticketId).not.toBe("")

        // Admin 在未分派工单中写入内部备注；公共队列 Agent 不得获知其存在。
        await roles.admin.page.goto(`/admin/tickets/${ticketId}`)
        await expect(roles.admin.page).toHaveURL(
          new RegExp(`/admin/tickets/${ticketId}(?:\\?|$)`),
        )
        await expect(roles.admin.page.getByText(title, { exact: true })).toBeVisible()
        await roles.admin.page
          .getByRole("tab", { name: "Internal note", exact: true })
          .click()
        await roles.admin.page
          .getByPlaceholder("Add context for the support team")
          .fill(adminOnlyNote)
        await roles.admin.page.getByRole("button", { name: "Add note" }).click()
        await expect(roles.admin.page.getByText(adminOnlyNote)).toBeVisible()

        const unassignedResponse = await request.get(
          `${apiBaseUrl}/api/v1/tickets/${ticketId}`,
          { headers: authHeaders(roles.agent.token) },
        )
        const unassignedPayload = await unassignedResponse.text()
        expect(unassignedResponse.ok(), unassignedPayload).toBeTruthy()
        expect(unassignedPayload).not.toContain(adminOnlyNote)
        expect(unassignedPayload).not.toContain("INTERNAL_NOTE")

        await roles.agent.page.goto(`/queue/${ticketId}`)
        await expect(roles.agent.page.getByText(title)).toBeVisible()
        await expect(
          roles.agent.page.getByText(adminOnlyNote),
        ).not.toBeVisible()
        await expect(
          roles.agent.page.getByRole("tab", { name: "Internal note" }),
        ).not.toBeVisible()
        await roles.agent.page
          .getByRole("button", { name: "Claim ticket" })
          .click()
        await expect(
          roles.agent.page.getByText(
            "Ticket claimed and added to your work queue.",
          ),
        ).toBeVisible()

        // 负责人 Agent 公开回复、添加内部备注，并请求客户补充信息。
        await roles.agent.page
          .getByPlaceholder("Share an update with the requester")
          .fill(agentReply)
        await roles.agent.page
          .getByRole("button", { name: "Send reply" })
          .click()
        await expect(roles.agent.page.getByText(agentReply)).toBeVisible()
        await roles.agent.page
          .getByRole("tab", { name: "Internal note", exact: true })
          .click()
        await roles.agent.page
          .getByPlaceholder("Add context for the support team")
          .fill(agentOnlyNote)
        await roles.agent.page.getByRole("button", { name: "Add note" }).click()
        await expect(roles.agent.page.getByText(agentOnlyNote)).toBeVisible()
        await selectOption(roles.agent.page, "Status", "Waiting for customer")
        await expect(
          roles.agent.page.getByText("Ticket status updated."),
        ).toBeVisible()

        // Customer 只能看到公开回复，回复后状态自动回到处理中。
        await roles.customer.page.goto(`/tickets/${ticketId}`)
        await expect(roles.customer.page.getByText(agentReply)).toBeVisible()
        await expect(
          roles.customer.page.getByText(adminOnlyNote),
        ).not.toBeVisible()
        await expect(
          roles.customer.page.getByText(agentOnlyNote),
        ).not.toBeVisible()
        await expect(
          roles.customer.page.getByText("Waiting for customer", {
            exact: true,
          }),
        ).toBeVisible()
        await roles.customer.page
          .getByPlaceholder("Share an update with the requester")
          .fill("Here are the requested customer details.")
        await roles.customer.page
          .getByRole("button", { name: "Send reply" })
          .click()
        await expect(
          roles.customer.page.getByText("In progress", { exact: true }),
        ).toBeVisible()

        // Agent 解决工单，Admin 随后转派、关闭并执行确认删除。
        await roles.agent.page.reload()
        await selectOption(roles.agent.page, "Status", "Resolved")
        await expect(
          roles.agent.page.getByText("Ticket status updated."),
        ).toBeVisible()

        await roles.admin.page.reload()
        await roles.admin.page
          .getByRole("button", { name: "Change assignee" })
          .click()
        const assignmentDialog = roles.admin.page.getByRole("dialog")
        await assignmentDialog.getByLabel("Agent").click()
        await roles.admin.page
          .getByRole("option", {
            name: roles.secondAgent.fullName,
            exact: true,
          })
          .click()
        await assignmentDialog
          .getByRole("button", { name: "Save assignment" })
          .click()
        await expect(
          roles.admin.page.getByText("Ticket reassigned."),
        ).toBeVisible()

        const oldAgentResponse = await request.get(
          `${apiBaseUrl}/api/v1/tickets/${ticketId}`,
          { headers: authHeaders(roles.agent.token) },
        )
        expect(oldAgentResponse.status()).toBe(403)

        await selectOption(roles.admin.page, "Status", "Closed")
        await expect(
          roles.admin.page.getByText("Ticket status updated."),
        ).toBeVisible()
        await expect(
          roles.admin.page.getByText("This ticket is closed and is read-only."),
        ).toBeVisible()

        await roles.customer.page.reload()
        await expect(
          roles.customer.page.getByText(
            "This ticket is closed and is read-only.",
          ),
        ).toBeVisible()
        await expect(
          roles.customer.page.getByRole("button", { name: "Send reply" }),
        ).not.toBeVisible()

        await roles.admin.page
          .getByRole("button", { name: "Delete ticket" })
          .click()
        const deleteDialog = roles.admin.page.getByRole("dialog")
        await deleteDialog.getByRole("checkbox").check()
        await deleteDialog
          .getByRole("button", { name: "Delete ticket" })
          .click()
        await expect(roles.admin.page).toHaveURL(/\/admin(?:\?|$)/)

        const deletedResponse = await request.get(
          `${apiBaseUrl}/api/v1/tickets/${ticketId}`,
          { headers: authHeaders(roles.admin.token) },
        )
        expect(deletedResponse.status()).toBe(404)

        // 仅剩一个活跃 Admin 时，后端必须拒绝自我降级。
        const adminResponse = await request.get(
          `${apiBaseUrl}/api/v1/users/me`,
          {
            headers: authHeaders(roles.admin.token),
          },
        )
        const adminUser = (await adminResponse.json()) as { id: string }
        const demoteResponse = await request.patch(
          `${apiBaseUrl}/api/v1/users/${adminUser.id}`,
          {
            headers: authHeaders(roles.admin.token),
            data: { role: "CUSTOMER" },
          },
        )
        expect(demoteResponse.status()).toBe(409)

        // 两个 Agent 并发接手同一新工单时只能有一个成功。
        const concurrentTicket = await request.post(
          `${apiBaseUrl}/api/v1/tickets`,
          {
            headers: authHeaders(roles.customer.token),
            data: {
              title: `Concurrent claim ${Date.now()}`,
              description: "Only one agent may claim this ticket.",
              category: "OTHER",
            },
          },
        )
        const concurrentPayload = (await concurrentTicket.json()) as {
          id: string
        }
        expect(concurrentTicket.ok(), JSON.stringify(concurrentPayload)).toBeTruthy()
        const concurrentId = concurrentPayload.id
        const claimResults = await Promise.all([
          request.post(`${apiBaseUrl}/api/v1/tickets/${concurrentId}/claim`, {
            headers: authHeaders(roles.agent.token),
          }),
          request.post(`${apiBaseUrl}/api/v1/tickets/${concurrentId}/claim`, {
            headers: authHeaders(roles.secondAgent.token),
          }),
        ])
        expect(
          claimResults.map((response) => response.status()).sort(),
        ).toEqual([200, 409])

        const adminClaimTicket = await request.post(
          `${apiBaseUrl}/api/v1/tickets`,
          {
            headers: authHeaders(roles.customer.token),
            data: {
              title: `Admin claim ${Date.now()}`,
              description: "Admin may claim an unassigned ticket.",
              category: "OTHER",
            },
          },
        )
        const adminClaimId = ((await adminClaimTicket.json()) as { id: string })
          .id
        const adminClaimResponse = await request.post(
          `${apiBaseUrl}/api/v1/tickets/${adminClaimId}/claim`,
          { headers: authHeaders(roles.admin.token) },
        )
        expect(adminClaimResponse.status()).toBe(200)
      } finally {
        await closeRoleContexts(roles)
      }
    })
})
