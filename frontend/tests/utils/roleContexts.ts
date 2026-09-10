// 为角色化 E2E 创建相互隔离的浏览器会话和 API 身份。by AI.Coding
import {
  type APIRequestContext,
  type Browser,
  type BrowserContext,
  expect,
  type Page,
} from "@playwright/test"

import { firstSuperuser, firstSuperuserPassword } from "../config.ts"
import { randomEmail, randomPassword } from "./random.ts"

const apiBaseUrl = process.env.VITE_API_URL ?? "http://localhost:8000"
const appBaseUrl = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173"

export type RoleIdentity = {
  email: string
  fullName: string
  password: string
  token: string
}

export type RoleSession = RoleIdentity & {
  context: BrowserContext
  page: Page
}

export type RoleContexts = {
  admin: RoleSession
  agent: RoleSession
  secondAgent: RoleSession
  customer: RoleSession
}

// 通过真实登录接口获取访问令牌，确保测试身份经过与页面一致的认证边界。
export async function logInThroughApi(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<string> {
  const response = await request.post(
    `${apiBaseUrl}/api/v1/login/access-token`,
    {
      form: { username: email, password },
    },
  )
  expect(response.ok(), await response.text()).toBeTruthy()
  const payload = (await response.json()) as { access_token: string }
  return payload.access_token
}

// Admin 通过正式用户管理接口创建指定角色，避免依赖开发专用私有接口。
async function createRoleUser(
  request: APIRequestContext,
  adminToken: string,
  role: "CUSTOMER" | "AGENT",
  label: string,
): Promise<RoleIdentity> {
  const email = randomEmail()
  const password = randomPassword()
  const fullName = `${label} ${Date.now()} ${Math.random().toString(36).slice(2, 7)}`
  const response = await request.post(`${apiBaseUrl}/api/v1/users/`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: {
      email,
      password,
      full_name: fullName,
      role,
      is_active: true,
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return {
    email,
    fullName,
    password,
    token: await logInThroughApi(request, email, password),
  }
}

// 每个角色使用独立 BrowserContext，防止 localStorage、缓存和导航状态跨账号泄漏。
async function openRoleSession(
  browser: Browser,
  identity: RoleIdentity,
): Promise<RoleSession> {
  const context = await browser.newContext({
    storageState: {
      cookies: [],
      origins: [
        {
          origin: appBaseUrl,
          localStorage: [
            { name: "access_token", value: identity.token },
          ],
        },
      ],
    },
  })
  return { ...identity, context, page: await context.newPage() }
}

// 统一创建完整三角色测试环境，并额外提供第二个 Agent 用于并发和转派验证。
export async function createRoleContexts(
  request: APIRequestContext,
  browser: Browser,
): Promise<RoleContexts> {
  const adminToken = await logInThroughApi(
    request,
    firstSuperuser,
    firstSuperuserPassword,
  )
  const adminIdentity: RoleIdentity = {
    email: firstSuperuser,
    fullName: "Initial Admin",
    password: firstSuperuserPassword,
    token: adminToken,
  }
  const [customerIdentity, agentIdentity, secondAgentIdentity] =
    await Promise.all([
      createRoleUser(request, adminToken, "CUSTOMER", "E2E Customer"),
      createRoleUser(request, adminToken, "AGENT", "E2E Agent"),
      createRoleUser(request, adminToken, "AGENT", "E2E Agent Two"),
    ])
  const [admin, customer, agent, secondAgent] = await Promise.all([
    openRoleSession(browser, adminIdentity),
    openRoleSession(browser, customerIdentity),
    openRoleSession(browser, agentIdentity),
    openRoleSession(browser, secondAgentIdentity),
  ])
  return { admin, customer, agent, secondAgent }
}

// 关闭所有角色上下文，确保每次测试释放浏览器资源。
export async function closeRoleContexts(contexts: RoleContexts): Promise<void> {
  await Promise.allSettled([
    contexts.admin.context.close(),
    contexts.customer.context.close(),
    contexts.agent.context.close(),
    contexts.secondAgent.context.close(),
  ])
}

export const authHeaders = (token: string) => ({
  Authorization: `Bearer ${token}`,
})

export { apiBaseUrl }
