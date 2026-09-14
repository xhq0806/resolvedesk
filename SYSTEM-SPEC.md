# ResolveDesk 系统行为规格

> 更新时间：2026-09-14
> 文档状态：已归档系统行为规格
> 当前归档：`changes/archive/2026-09-14-conversation-avatars/`
> 规格依据：`changes/archive/2026-09-14-conversation-avatars/spec.md`

## 1. 文档目的

本文档描述 ResolveDesk 当前系统行为，用于后续需求分析、coding、review 和 verify。已归档需求的完整上下文保存在 `changes/archive/`。

状态标记：

- **已实现基线**：当前代码中已有，后续改动不得破坏。
- **本期目标**：本次 coding 需要实现并验收。
- **明确排除**：本期不做，不能在 coding 中擅自加入。

## 2. 产品定位

ResolveDesk 是带 AI Agent 的 Workspace 级客服工单平台。客户优先通过右下角“在线咨询”与 AI Agent 对话；AI Agent 基于当前 Workspace 的知识库回答问题。客户需要人工服务时，系统将咨询会话转为工单，并尝试自动分派给可用人工客服。Admin 管理知识库、AI 配置、用户和全局工单；Agent 只处理自己负责或公共队列中的工单。

## 3. 技术与运行能力

| 能力 | 状态 | 系统行为 |
|---|---|---|
| 后端 API | 已实现基线 | FastAPI 提供 `/api/v1` HTTP API 和 OpenAPI 文档 |
| 数据库 | 已实现基线 | PostgreSQL + SQLModel，结构变更由 Alembic 管理 |
| 前端 | 已实现基线 | React、TypeScript、Vite、TanStack Router、TanStack Query |
| 鉴权 | 已实现基线 | 邮箱密码登录，Bearer JWT 访问受保护接口 |
| Workspace | 已实现基线 | 请求通过 `X-Workspace-ID` 绑定当前 Workspace，并校验成员关系 |
| AI/RAG | 已实现基线 | 支持 Provider 配置、知识库入库、向量检索、AI 会话和 SSE run |
| 在线咨询 | 已实现基线 | Customer 通过悬浮入口使用 AI Agent，对话可转人工生成工单 |
| 自动分派 | 已实现基线 | 转人工工单优先分派给当前 Workspace 可用 Agent |
| 用户头像 | 已实现基线 | 用户资料支持头像 URL，侧边栏、工单、在线咨询展示头像并提供兜底 |

## 4. Workspace 与角色

### 4.1 Workspace 边界

- 所有工单、消息、审计、知识文档、AI 配置、AI 会话、附件和工具调用都必须归属于一个 Workspace。
- 用户只能访问自己拥有 ACTIVE 成员关系的 Workspace。
- 用户可在自己所属的 ACTIVE Workspace 之间切换；切换后前端必须清理或重新拉取 Workspace 级缓存。
- 跨 Workspace 资源访问必须返回统一资源错误，不泄露资源标题、编号、文档名或存在性。

### 4.2 角色定义

| 角色 | 定义 | 核心职责 |
|---|---|---|
| `CUSTOMER` | 客户 | 在线咨询、创建/查看/回复自己的工单、请求转人工 |
| `AGENT` | 人工客服 | 处理公共队列和分派给自己的工单 |
| `ADMIN` | 管理员 | 管理用户、全局工单、知识库、AI Provider 和工具权限 |
| `OWNER` | Workspace 所有者 | Workspace 管理权限；产品文案中归入 Admin 管理者 |

约束：

- Agent 是人工客服，不是 AI Agent。
- AI Agent 是 Workspace 内的独立执行主体，不是登录用户。
- Admin/Owner 是知识库和 AI 配置的管理者。
- Customer 和 Agent 不得直接浏览或管理知识库。
- 系统必须保留至少一个可管理当前 Workspace 的 Owner/Admin。

## 5. 角色权限

### 5.1 Customer

Customer 可以：

- 查看和修改自己的资料与密码；
- 设置、修改或清除自己的头像 URL；
- 在右下角打开“在线咨询”面板；
- 与 AI Agent 对话，并查看回答、来源摘要和失败提示；
- 请求转人工，由系统创建工单；
- 查看、筛选、搜索和回复自己的工单；
- 查看自己工单的公开时间线。

Customer 不可以：

- 查看其他客户的工单；
- 查看内部备注；
- 查看 Agent 队列或 Admin 用户管理；
- 查看知识库侧边栏入口；
- 访问知识库列表、上传、删除、重试或后台检索接口；
- 管理 AI Provider、工具权限、Workspace 成员或用户角色。

### 5.2 Agent

Agent 可以：

- 设置、修改或清除自己的头像 URL；
- 查看未分派公共队列；
- 查看分派给自己的工单；
- 接手未分派且未关闭工单；
- 对自己负责的未关闭工单发送公开回复；
- 对自己负责的未关闭工单添加内部备注；
- 修改自己负责工单的状态、优先级和分类；
- 查看转人工工单中的 AI 会话摘要和客户公开上下文。

Agent 不可以：

- 查看其他 Agent 已负责的工单；
- 把工单转派给其他 Agent；
- 取消工单分派；
- 管理用户、角色、启用状态或 Workspace 成员；
- 查看知识库侧边栏入口；
- 浏览、上传、删除、重试或管理知识库文档；
- 配置 AI Provider 或工具权限；
- 删除工单。

### 5.3 Admin/Owner

Admin/Owner 可以：

- 设置、修改或清除自己的头像 URL；
- 查看、筛选和搜索当前 Workspace 内全部工单；
- 分派、转派、取消分派、关闭和删除工单；
- 对未关闭工单发送公开回复和内部备注；
- 管理用户角色和启用状态；
- 管理 Workspace 知识库：上传、查看状态、删除、重试；
- 配置 AI Provider 和 AI Agent 工具权限；
- 查看 AI 会话、工具调用、转人工和审计记录。

Admin/Owner 不可以：

- 让 Workspace 失去最后一个 Owner/Admin；
- 修改 `CLOSED` 工单的业务内容；
- 将工单分派给 Customer、停用用户或非当前 Workspace 成员；
- 让 AI Agent 删除工单、管理成员或修改 Provider 配置。

## 6. 知识库与 RAG

### 6.1 知识库管理

- 知识库是 Workspace 级后台资产。
- 只有 Admin/Owner 可以看到侧边栏“知识库”入口。
- 只有 Admin/Owner 可以上传文档、查看摄取状态、删除文档和重试失败任务。
- Agent/Customer 侧边栏完全不显示“知识库”。
- Agent/Customer 直接访问 `/knowledge` 不得展示文档列表、上传控件、删除或重试按钮。

### 6.2 AI Agent 使用知识库

- AI Agent 可在服务端内部检索当前 Workspace 的 `READY` 文档。
- 检索必须带 `workspace_id`，不能跨 Workspace 使用文档。
- 文档中的内容只作为资料，不得改变系统权限或工具授权。
- Customer 只能看到 AI 回答和被授权的来源摘要。
- 来源摘要可以包含文档名、定位和短预览，但不能提供知识库管理入口。
- 无可靠依据时，AI 必须说明无法从知识库确认，并提供转人工入口。

## 7. Customer 在线咨询

### 7.1 前端入口

- Customer 登录后，在应用右下角看到“在线咨询”悬浮按钮。
- Agent/Admin 不显示该悬浮按钮。
- 点击按钮打开咨询面板，不离开当前页面。
- 面板包含标题、关闭按钮、推荐问题、带头像的消息列表、输入框、发送按钮和“转人工”入口。
- 面板必须有加载、发送中、失败、空会话和无依据状态。
- 移动端和桌面端均不得遮挡主要导航和关键操作。

### 7.2 对话行为

- Customer 发送消息后，系统在当前 Workspace 创建或复用该 Customer 的 AI conversation。
- Customer 消息显示当前用户头像；AI Agent 回复显示固定 AI 头像，头像不可用时显示可见 `AI` 兜底。
- 同一 conversation 同时只允许一个 AI run 处于生成中。
- AI 回复以流式事件展示文本、来源、完成和失败状态。
- 客户端断开或用户取消时，不得生成半条完整 AI 回复。
- Provider 未配置、鉴权失败、超时或返回异常时，面板显示稳定失败提示。

## 8. 转人工与工单分派

### 8.1 转人工触发

Customer 可以通过以下方式请求转人工：

- 点击咨询面板中的“转人工”；
- 输入明确转人工意图，由系统识别并要求确认。

触发后：

- 系统基于当前 AI conversation 创建工单；
- 工单标题和描述包含客户问题、AI 对话摘要和转人工原因；
- conversation 标记为已转人工并关联 ticket；
- 重复转人工请求必须返回同一个 ticket，不得创建重复工单。

### 8.2 自动分派

- 系统只在当前 Workspace 中选择候选 Agent。
- 候选 Agent 必须是 ACTIVE Workspace 成员、全局用户 active、成员角色为 `AGENT`。
- 第一版分派策略为：选择未关闭负责工单数最少的 Agent；数量相同按稳定顺序选择。
- 有候选 Agent 时，新工单分派给该 Agent，状态进入 `IN_PROGRESS`。
- 没有候选 Agent 时，新工单保持未分派 `OPEN`，进入公共队列。
- 分派、未分派和转人工创建均必须写入审计。

### 8.3 Agent 人工处理

- 被分派 Agent 可以查看工单详情、客户公开消息、AI 会话摘要和转人工原因。
- Agent 可以发送公开回复、添加内部备注、修改状态、优先级和分类。
- Agent 仍不得管理知识库、Provider、工具权限、用户或其他 Agent 工单。

## 9. 工单行为

固定状态：

- `OPEN`
- `IN_PROGRESS`
- `WAITING_FOR_CUSTOMER`
- `RESOLVED`
- `CLOSED`

状态机：

```text
OPEN
  └─ Agent 接手 / Admin 分派 / 转人工自动分派 -> IN_PROGRESS

IN_PROGRESS
  ├─ 负责 Agent/Admin 请求客户补充 -> WAITING_FOR_CUSTOMER
  └─ 负责 Agent/Admin 确认解决 -> RESOLVED

WAITING_FOR_CUSTOMER
  ├─ Customer 公开回复 -> IN_PROGRESS
  ├─ 负责 Agent/Admin 恢复处理 -> IN_PROGRESS
  └─ 负责 Agent/Admin 确认解决 -> RESOLVED

RESOLVED
  ├─ Customer 公开回复 -> IN_PROGRESS
  ├─ Admin 重新打开 -> IN_PROGRESS
  └─ Admin 确认结束 -> CLOSED

CLOSED
  └─ 不允许继续变更
```

补充规则：

- 未分派转人工工单进入公共队列，状态为 `OPEN`。
- 自动分派成功的转人工工单状态为 `IN_PROGRESS`。
- `CLOSED` 工单只读。
- 不符合状态机的请求必须拒绝，且不能部分更新。

## 10. 用户头像

- 所有登录角色都可以在个人资料中设置、修改或清除自己的头像 URL。
- 头像 URL 是用户公开资料字段，可出现在当前用户响应、用户列表、工单 requester、assignee、message author 和 audit actor 摘要中。
- 第一版头像只支持 `http://` 或 `https://` 外链 URL；空值表示未设置头像。
- 前端在侧边栏用户菜单、工单列表客户/负责人列、工单时间线、在线咨询用户消息中展示用户头像。
- 用户头像缺失或图片加载失败时，前端必须显示姓名或邮箱首字母兜底。
- AI Agent 在在线咨询中使用固定系统头像；头像兜底必须可见显示 `AI`。
- 本能力不包含本地文件上传、图片裁剪、对象存储、CDN 或 Workspace 级独立头像。

## 11. 前端导航

Customer 登录后主要看到：

- 工作台；
- 我的工单；
- 设置；
- 右下角“在线咨询”悬浮入口。

Agent 登录后主要看到：

- 工作台；
- 客服队列；
- 设置。

Admin/Owner 登录后主要看到：

- 工作台；
- AI 工作台；
- 知识库；
- 全部工单；
- 用户管理；
- 设置。

前端规则：

- 无权功能不显示在导航和操作区。
- 直接输入无权路由时不得显示受保护数据。
- 前端隐藏不能替代后端权限校验。
- Workspace 切换后不得展示上一 Workspace 的缓存数据。

## 12. 测试与验收基线

### 后端必须覆盖

- Workspace 成员校验和跨 Workspace 资源拒绝；
- Admin/Owner 可管理知识库；
- Agent/Customer 调用知识库管理接口被拒绝；
- Customer 专用 AI conversation 创建和消息流；
- AI RAG 仅使用当前 Workspace `READY` 文档；
- 无依据回答不编造来源；
- 转人工创建工单；
- 转人工重复请求幂等；
- 有可用 Agent 时自动分派；
- 无可用 Agent 时进入未分派队列；
- Agent 处理转人工工单的权限边界；
- 工单状态机和审计回归。
- 用户头像 URL 可保存、读取、清空并随用户摘要返回。

### 前端 E2E 必须覆盖

- Customer 侧边栏不显示知识库；
- Agent 侧边栏不显示知识库；
- Admin/Owner 侧边栏显示知识库并可进入；
- Agent/Customer 直接访问 `/knowledge` 不显示文档管理内容；
- Customer 可打开“在线咨询”浮窗；
- Customer 可发送问题并看到 AI 回答和来源摘要；
- Customer 可请求转人工并看到工单编号；
- 有 Agent 时工单进入该 Agent 工作范围；
- 无 Agent 时工单进入公共队列；
- 重复点击转人工不创建重复工单。
- 个人资料页可编辑头像 URL 并显示预览；
- 侧边栏、工单列表、工单时间线和在线咨询均显示头像；
- 用户头像缺失或加载失败时显示首字母，AI 头像兜底显示 `AI`。

### 运行验收

- 后端测试通过；
- 后端 lint、类型检查和 OpenAPI 契约通过；
- 前端 TypeScript 构建通过；
- Playwright 关键流程通过；
- Docker Compose 启动和健康检查通过。

## 13. 明确排除范围

本期不包含：

- 复杂客服团队、客服组长、技能组路由；
- Agent 在线状态心跳、排班和值班表；
- SLA、自动升级、满意度评价；
- 邮件收件转工单；
- 计费和生产级合规认证；
- 跨 Workspace 知识共享；
- Customer/Agent 直接浏览知识库；
- 人工客服实时 IM 替代工单；
- AI 删除工单、管理成员、修改 Provider 或绕过工具授权；
- 本地头像上传、图片裁剪、对象存储、CDN 和 Workspace 级独立头像。

## 14. 归档状态

本规格已完成二期 Delta 归档。归档内容包括：

- Admin/Owner-only 知识库权限；
- Customer 右下角“在线咨询”入口；
- Customer 专用 AI conversation 与服务端内部 RAG；
- 转人工创建工单、幂等关联 conversation 和自动分派；
- Agent 查看转人工上下文并按既有工单权限处理；
- 用户头像 URL 设置、持久化和会话/工单头像展示。

后续需求若修改以上行为，必须在新的 `changes/active/` 目录中通过 proposal、spec、design、coding、review、archive 流程更新本文件。
