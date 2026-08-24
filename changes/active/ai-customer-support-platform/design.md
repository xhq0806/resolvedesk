> 来源：spec.md
> 生成时间：2026-08-21
> 阶段：design
> 需求目录：`changes/active/ai-customer-support-platform/`

# ResolveDesk 全栈一期技术设计

## Why

### 背景与现状

当前后端是同步 FastAPI + SQLModel 应用。`backend/app/models.py` 同时承载 ORM 模型和 API Schema，`items.py`、`users.py` 直接查询数据库并在路由中提交事务。该结构能够支撑模板 CRUD，但无法安全承载本期的状态机、角色授权、原子接手、操作审计和删除保留：一次业务动作需要同时修改工单并写入审计记录，任何部分提交都会破坏业务一致性。

当前前端使用 React、TanStack Router、TanStack Query、TanStack Table 和 OpenAPI 生成客户端。现有 `DataTable` 只执行客户端分页，静态查询键也不包含筛选条件；本期必须升级为服务端分页和角色化路由。现有 Items 业务将在后端、前端和测试中整体退出，不迁移其示例数据。

设计复杂度判定为 **S2**：系统包含多资源、三角色、跨用户访问控制、状态流转、并发接手、审计和数据库迁移。因此后端采用 route、service、repository、ORM model、API schema 分层，同时保持单体应用和单 PostgreSQL，不引入队列、缓存或微服务。

### 设计目标 / 非目标

| 类型 | 说明 |
|---|---|
| ✅ 目标 | 在单工作空间内实现 Customer、Agent、Admin 单角色 RBAC，并由后端统一执行资源级权限 |
| ✅ 目标 | 实现 Ticket、TicketMessage、TicketAuditLog 领域模型和完整状态机 |
| ✅ 目标 | 通过单事务保证工单修改与审计记录同时成功或同时失败 |
| ✅ 目标 | 通过 PostgreSQL 条件更新保证并发接手最多一个请求成功 |
| ✅ 目标 | 通过软删除实现“业务不可恢复、业务查询不可见、删除审计保留” |
| ✅ 目标 | 保留现有认证、密码重置、邮件、OpenAPI 客户端、Docker 和 CI 基础能力 |
| ✅ 目标 | 后端契约稳定并通过测试后，再生成客户端并开发角色化前端 |
| ❌ 非目标 | 不设计 Workspace、多租户、团队、客服组长和团队队列 |
| ❌ 非目标 | 不设计 AI Copilot、RAG、知识库、Tool Calling 或任何模型调用 |
| ❌ 非目标 | 不设计附件、SLA、实时聊天、邮件转工单、标签、自定义字段和复杂报表 |
| ❌ 非目标 | 不引入 Redis、Celery、消息队列、WebSocket、微服务或第二套 HTTP Client |

## What

## 1. 总体架构

### 1.1 后端模块

| 模块 | 职责 | 依赖 |
|---|---|---|
| `app/api/routes` | 声明 HTTP 路径、输入输出、依赖和状态码；映射领域错误 | `schemas`、`services`、`api/deps` |
| `app/api/deps.py` | 获取 Session、当前活跃用户、Admin 角色依赖 | `core/security`、`models/user` |
| `app/models` | ORM 表、数据库枚举、关系和持久化字段 | SQLModel、SQLAlchemy |
| `app/schemas` | 请求、响应、分页、筛选和错误响应 Schema | Pydantic、领域枚举 |
| `app/services/user_service.py` | 用户创建、角色启停、最后活跃 Admin 保护 | `repositories/user_repository` |
| `app/services/ticket_service.py` | 工单权限、状态机、接手分派、消息、属性修改、删除和审计编排 | Ticket/User repository |
| `app/services/statistics_service.py` | 按角色生成统计结果 | `repositories/ticket_repository` |
| `app/repositories` | 角色化查询、聚合查询、条件更新、行锁和持久化 | SQLModel Session |
| `app/core/errors.py` | 稳定领域异常和 API 错误码 | 无业务模块依赖 |
| `app/core/request_context.py` | 创建并传递 `request_id` | FastAPI middleware/contextvars |

```text
HTTP Request
   ↓
FastAPI route ── CurrentUser / Admin dependency
   ↓
Service（权限 + 状态机 + 事务边界 + 审计）
   ↓
Repository（查询 + 条件更新 + 行锁）
   ↓
PostgreSQL
```

### 1.2 前端模块

| 模块 | 职责 | 依赖 |
|---|---|---|
| 文件路由 | 登录保护、角色保护、URL 查询参数和页面装配 | TanStack Router |
| `hooks/useAuth.ts` | 当前用户缓存、登录后刷新、登出清理 | OpenAPI Client、TanStack Query |
| `lib/routeGuards.ts` | 根据 `UserRole` 统一执行页面角色判断 | Current user query |
| `lib/ticketQueries.ts` | 统一 Ticket 查询键和 query options | 生成客户端 |
| `components/Common/DataTable.tsx` | 受控服务端分页表格 | TanStack Table |
| `components/Tickets` | 工单筛选、表格、详情、时间线、回复和操作组件 | 生成客户端、UI primitives |
| `components/Admin` | 用户角色和启停管理 | 生成客户端 |
| Playwright tests | 使用独立三角色上下文验证业务闭环 | UI、测试 API helper |

```text
Route search params
   ↓
Query options + OpenAPI generated client
   ↓
Role-specific page
   ↓
Shared Ticket components / Server DataTable
   ↓
Mutation → invalidate list/detail/timeline/statistics keys
```

## 2. 后端数据模型

### 2.1 枚举

数据库枚举使用字符串值，API 使用相同值，避免数据库值与前端值转换漂移。

| 枚举 | 值 |
|---|---|
| `UserRole` | `CUSTOMER`、`AGENT`、`ADMIN` |
| `TicketStatus` | `OPEN`、`IN_PROGRESS`、`WAITING_FOR_CUSTOMER`、`RESOLVED`、`CLOSED` |
| `TicketPriority` | `LOW`、`MEDIUM`、`HIGH`、`URGENT` |
| `TicketCategory` | `ACCOUNT`、`BILLING`、`PRODUCT`、`BUG`、`FEATURE_REQUEST`、`OTHER` |
| `TicketMessageType` | `PUBLIC_REPLY`、`INTERNAL_NOTE` |
| `TicketAuditAction` | `TAKEN`、`ASSIGNED`、`REASSIGNED`、`UNASSIGNED`、`STATUS_CHANGED`、`PRIORITY_CHANGED`、`CATEGORY_CHANGED`、`DELETED` |

### 2.2 表结构变更

| 操作 | 表/实体 | 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|---|---|
| 修改 | `user` | `role` | `UserRole` | NOT NULL，默认 `CUSTOMER`，索引 | 替代业务上的 `is_superuser` |
| 删除 | `user` | `is_superuser` | Boolean | 迁移完成后删除 | 先回填 `role`，再删除旧字段 |
| 保留 | `user` | `is_active` | Boolean | NOT NULL | 控制登录及业务访问 |
| 新增 | `ticket` | `id` | UUID | PK | 工单内部标识 |
| 新增 | `ticket` | `ticket_number` | VARCHAR(40) | UNIQUE、NOT NULL、不可更新 | 使用 `TKT-` + 完整 UUID 十六进制生成，避免额外序列表 |
| 新增 | `ticket` | `title` | VARCHAR(200) | NOT NULL | 去除首尾空白后校验 |
| 新增 | `ticket` | `description` | TEXT | NOT NULL | 1～10,000 字符 |
| 新增 | `ticket` | `status` | `TicketStatus` | NOT NULL，默认 `OPEN`，索引 | 状态机字段 |
| 新增 | `ticket` | `priority` | `TicketPriority` | NOT NULL，默认 `MEDIUM`，索引 | 工单优先级 |
| 新增 | `ticket` | `category` | `TicketCategory` | NOT NULL，索引 | 工单分类 |
| 新增 | `ticket` | `requester_id` | UUID | FK `user.id`、NOT NULL、RESTRICT、索引 | 创建工单的 Customer |
| 新增 | `ticket` | `assignee_id` | UUID nullable | FK `user.id`、RESTRICT、索引 | 当前 Agent |
| 新增 | `ticket` | `created_at` | timestamptz | NOT NULL | UTC 创建时间 |
| 新增 | `ticket` | `updated_at` | timestamptz | NOT NULL、索引 | 列表默认排序依据 |
| 新增 | `ticket` | `deleted_at` | timestamptz nullable | 索引 | 产品级不可恢复软删除标记 |
| 新增 | `ticket` | `deleted_by_id` | UUID nullable | FK `user.id`、RESTRICT | 删除操作者 |
| 新增 | `ticket_message` | `id` | UUID | PK | 消息标识 |
| 新增 | `ticket_message` | `ticket_id` | UUID | FK `ticket.id`、NOT NULL、RESTRICT、索引 | 所属工单 |
| 新增 | `ticket_message` | `author_id` | UUID | FK `user.id`、NOT NULL、RESTRICT | 消息作者 |
| 新增 | `ticket_message` | `message_type` | `TicketMessageType` | NOT NULL、索引 | 公开回复或内部备注 |
| 新增 | `ticket_message` | `content` | TEXT | NOT NULL | 1～10,000 字符 |
| 新增 | `ticket_message` | `created_at` | timestamptz | NOT NULL、索引 | 时间线排序 |
| 新增 | `ticket_audit_log` | `id` | UUID | PK | 审计记录标识 |
| 新增 | `ticket_audit_log` | `ticket_id` | UUID | FK `ticket.id`、NOT NULL、RESTRICT、索引 | 软删除后仍保留关联 |
| 新增 | `ticket_audit_log` | `actor_id` | UUID | FK `user.id`、NOT NULL、RESTRICT | 操作者 |
| 新增 | `ticket_audit_log` | `action` | `TicketAuditAction` | NOT NULL、索引 | 操作类型 |
| 新增 | `ticket_audit_log` | `old_value` | JSON nullable | — | 变更前结构化快照 |
| 新增 | `ticket_audit_log` | `new_value` | JSON nullable | — | 变更后结构化快照 |
| 新增 | `ticket_audit_log` | `created_at` | timestamptz | NOT NULL、索引 | 操作时间 |
| 删除 | `item` | 整表 | — | — | 示例数据不迁移；迁移中删除表 |

### 2.3 索引

| 索引 | 字段 | 用途 |
|---|---|---|
| `ux_ticket_ticket_number` | `ticket_number` UNIQUE | 工单编号查询和唯一性 |
| `ix_ticket_requester_updated` | `requester_id, deleted_at, updated_at DESC` | Customer 列表 |
| `ix_ticket_assignee_updated` | `assignee_id, deleted_at, updated_at DESC` | Agent 本人列表 |
| `ix_ticket_queue_updated` | `assignee_id, status, deleted_at, updated_at DESC` | 未分派队列和状态筛选 |
| `ix_ticket_filter` | `status, priority, category, deleted_at` | Admin 组合筛选 |
| `ix_ticket_message_timeline` | `ticket_id, created_at ASC` | 消息时间线 |
| `ix_ticket_audit_timeline` | `ticket_id, created_at ASC` | 操作记录时间线 |
| `ix_user_role_active` | `role, is_active` | Agent 选择器和活跃 Admin 检查 |

不为消息正文建立全文索引，因为 spec 明确不搜索消息正文。标题和工单编号第一期使用大小写不敏感包含查询；数据规模未达到引入 PostgreSQL trigram 索引的必要条件。

### 2.4 实体关系

```text
User 1 ── N Ticket(requester)
User 1 ── N Ticket(assignee, nullable)
User 1 ── N TicketMessage(author)
User 1 ── N TicketAuditLog(actor)
Ticket 1 ── N TicketMessage
Ticket 1 ── N TicketAuditLog
```

用户、消息和审计不使用级联删除。业务已经禁止删除存在历史的用户；外键采用 `RESTRICT` 防止误删历史身份。Ticket 使用软删除，因此 Message 和 AuditLog 始终保留。

## 3. 后端 Schema 设计

### 3.1 用户 Schema

| Schema | 关键字段 | 用途 |
|---|---|---|
| `UserCreate` | `email, password, full_name?, role?, is_active?` | Admin 创建用户；公开注册不使用可选角色字段 |
| `UserRegister` | `email, password, full_name?` | 公开注册，后端固定角色为 Customer |
| `UserUpdateAdmin` | `email?, full_name?, role?, is_active?, password?` | Admin 修改其他用户 |
| `UserUpdateMe` | `email?, full_name?` | 用户修改自己，不允许角色和状态字段 |
| `UserPublic` | `id, email, full_name, role, is_active, created_at` | 当前用户和用户管理响应 |
| `UsersPublic` | `data, count` | 用户分页响应 |

所有外部输入 Schema 配置 `extra="forbid"`。公开注册即使提交 `role` 也会被拒绝，而不是静默忽略。

### 3.2 工单 Schema

| Schema | 关键字段 | 用途 |
|---|---|---|
| `TicketCreate` | `title, description, category` | Customer 创建工单 |
| `TicketPublic` | 工单基础字段、requester 摘要、assignee 摘要 | 列表项 |
| `TicketDetailPublic` | `TicketPublic + messages + audit_logs` | 按角色裁剪后的详情 |
| `TicketsPublic` | `data, count, page, page_size` | 服务端分页响应 |
| `TicketFilters` | `status?, priority?, category?, assignee_id?, query?, page, page_size` | 查询参数 |
| `TicketAssign` | `assignee_id` | Admin 分派和转派 |
| `TicketStatusUpdate` | `status` | 主动状态变更 |
| `TicketAttributesUpdate` | `priority?, category?` | 属性修改，至少提供一个字段 |
| `TicketMessageCreate` | `message_type, content` | Agent/Admin 消息创建 |
| `CustomerReplyCreate` | `content` | Customer 公开回复，类型由服务端固定 |
| `TicketMessagePublic` | `id, author, message_type, content, created_at` | 时间线消息 |
| `TicketAuditPublic` | `id, action, actor, old_value, new_value, created_at` | 按角色裁剪后的审计项 |
| `TicketStatisticsPublic` | 角色对应计数字段 | Dashboard 统计 |
| `DeleteTicketRequest` | `confirm: Literal[true]` | 明确删除确认 |

`TicketDetailPublic` 不能先组装完整内部数据再由前端过滤。Service 根据当前角色和负责人关系决定 repository 查询的消息类型，并生成已裁剪响应。

## 4. 后端服务与 Repository 签名

> 以下只定义公开签名和职责，不包含实现。

### 4.1 领域错误

```python
class AppError(Exception): ...
class NotFoundError(AppError): ...
class ForbiddenError(AppError): ...
class ConflictError(AppError): ...
class ValidationError(AppError): ...
```

统一错误响应：

```python
class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
```

### 4.2 UserRepository

```python
class UserRepository:
    def get_by_id(self, user_id: UUID, *, for_update: bool = False) -> User | None: ...
    def get_by_email(self, email: str) -> User | None: ...
    def list_users(self, filters: UserFilters) -> tuple[list[User], int]: ...
    def list_active_agents(self) -> list[User]: ...
    def lock_active_admins(self) -> list[User]: ...
    def add(self, user: User) -> None: ...
```

`lock_active_admins()` 使用数据库行锁锁定全部活跃 Admin，并按主键固定排序，避免两个 Admin 并发降级导致系统失去最后活跃 Admin。

### 4.3 TicketRepository

```python
class TicketRepository:
    def add(self, ticket: Ticket) -> None: ...
    def get_active_by_id(self, ticket_id: UUID, *, for_update: bool = False) -> Ticket | None: ...
    def get_active_by_number(self, ticket_number: str) -> Ticket | None: ...
    def list_for_actor(self, actor: User, filters: TicketFilters) -> tuple[list[Ticket], int]: ...
    def claim_if_available(self, ticket_id: UUID, agent_id: UUID, updated_at: datetime) -> Ticket | None: ...
    def list_messages(self, ticket_id: UUID, *, include_internal: bool) -> list[TicketMessage]: ...
    def list_audits(self, ticket_id: UUID, *, customer_safe_only: bool) -> list[TicketAuditLog]: ...
    def add_message(self, message: TicketMessage) -> None: ...
    def add_audit(self, audit: TicketAuditLog) -> None: ...
    def get_statistics(self, actor: User) -> TicketStatisticsRow: ...
```

`claim_if_available()` 必须是单条条件更新：仅当工单未删除、`status=OPEN` 且 `assignee_id IS NULL` 时更新负责人和状态，并通过受影响行或 `RETURNING` 判断成功。不得采用先读取再覆盖的读改写方式。

### 4.4 UserService

```python
class UserService:
    def register_customer(self, payload: UserRegister) -> UserPublic: ...
    def create_user(self, actor: User, payload: UserCreate) -> UserPublic: ...
    def list_users(self, actor: User, filters: UserFilters) -> UsersPublic: ...
    def update_user(self, actor: User, user_id: UUID, payload: UserUpdateAdmin) -> UserPublic: ...
    def update_me(self, actor: User, payload: UserUpdateMe) -> UserPublic: ...
```

`update_user()` 在角色或启用状态会使目标用户不再是活跃 Admin 时，先调用 `lock_active_admins()`，在同一事务中验证修改后仍至少存在一个活跃 Admin。

### 4.5 TicketService

```python
class TicketService:
    def create_ticket(self, actor: User, payload: TicketCreate) -> TicketDetailPublic: ...
    def list_tickets(self, actor: User, filters: TicketFilters) -> TicketsPublic: ...
    def get_ticket(self, actor: User, ticket_id: UUID) -> TicketDetailPublic: ...
    def claim_ticket(self, actor: User, ticket_id: UUID) -> TicketDetailPublic: ...
    def assign_ticket(self, actor: User, ticket_id: UUID, payload: TicketAssign) -> TicketDetailPublic: ...
    def unassign_ticket(self, actor: User, ticket_id: UUID) -> TicketDetailPublic: ...
    def add_customer_reply(self, actor: User, ticket_id: UUID, payload: CustomerReplyCreate) -> TicketMessagePublic: ...
    def add_staff_message(self, actor: User, ticket_id: UUID, payload: TicketMessageCreate) -> TicketMessagePublic: ...
    def update_status(self, actor: User, ticket_id: UUID, payload: TicketStatusUpdate) -> TicketDetailPublic: ...
    def update_attributes(self, actor: User, ticket_id: UUID, payload: TicketAttributesUpdate) -> TicketDetailPublic: ...
    def delete_ticket(self, actor: User, ticket_id: UUID, payload: DeleteTicketRequest) -> None: ...
```

每个写方法拥有一个显式事务边界：业务修改、`updated_at` 和审计插入在同一事务中完成；发生领域错误或数据库错误时统一回滚。Route 不调用 `commit()`。

### 4.6 StatisticsService

```python
class StatisticsService:
    def get_ticket_statistics(self, actor: User) -> TicketStatisticsPublic: ...
```

统计查询先应用角色数据范围，再聚合；不允许先统计全局数据后在应用层裁剪。

### 4.7 权限策略

Service 内部使用纯函数策略，便于 TDD：

```python
def can_view_ticket(actor: User, ticket: Ticket) -> bool: ...
def can_view_internal_notes(actor: User, ticket: Ticket) -> bool: ...
def can_reply_publicly(actor: User, ticket: Ticket) -> bool: ...
def can_add_internal_note(actor: User, ticket: Ticket) -> bool: ...
def can_manage_ticket(actor: User, ticket: Ticket) -> bool: ...
def allowed_status_targets(actor: User, ticket: Ticket) -> set[TicketStatus]: ...
```

关键规则：

- Customer：仅 requester 匹配。
- Agent：未分派或 assignee 匹配时可看基础信息；只有 assignee 匹配时可看内部备注并执行写操作。
- Admin：可看全部未删除工单及内部备注。
- Closed：所有业务写操作拒绝。
- 已删除：所有普通业务查询统一视为不存在。

## 5. HTTP API 契约

统一前缀为 `/api/v1`。成功响应显式声明状态码；错误响应使用 `ErrorResponse`。路径使用复数名词，非 CRUD 行为使用动作子路径。

### 5.1 用户接口

| 接口 | 方法 | 路径 | 入参 | 出参 | 主要错误 |
|---|---|---|---|---|---|
| 当前用户 | GET | `/users/me` | — | `UserPublic` | 401/403 |
| 更新自己 | PATCH | `/users/me` | `UserUpdateMe` | `UserPublic` | 409 email 重复 |
| 修改密码 | PATCH | `/users/me/password` | `UpdatePassword` | `Message` | 400 当前密码错误 |
| 公开注册 | POST | `/users/signup` | `UserRegister` | `UserPublic`，201 | 409 email 重复 |
| 用户列表 | GET | `/users` | `role?, is_active?, query?, page, page_size` | `UsersPublic` | 403 非 Admin |
| Admin 创建用户 | POST | `/users` | `UserCreate` | `UserPublic`，201 | 403、409 |
| 查询用户 | GET | `/users/{user_id}` | path UUID | `UserPublic` | 403、404 |
| Admin 更新用户 | PATCH | `/users/{user_id}` | `UserUpdateAdmin` | `UserPublic` | 403、404、409 最后 Admin |
| 活跃 Agent 选项 | GET | `/users/agents` | — | `list[UserSummary]` | 403 非 Admin |

不保留用户物理删除接口。`DELETE /users/me` 和 `DELETE /users/{user_id}` 从 OpenAPI 中移除；账户终止通过 Admin 停用实现。

### 5.2 工单接口

| 接口 | 方法 | 路径 | 入参 | 出参 | 主要错误 |
|---|---|---|---|---|---|
| 创建工单 | POST | `/tickets` | `TicketCreate` | `TicketDetailPublic`，201 | 403 非 Customer、422 |
| 工单列表 | GET | `/tickets` | `TicketFilters` | `TicketsPublic` | 422 无效筛选 |
| 工单详情 | GET | `/tickets/{ticket_id}` | UUID | `TicketDetailPublic` | 403、404 |
| Agent/Admin 接手 | POST | `/tickets/{ticket_id}/claim` | — | `TicketDetailPublic` | 403、404、409 |
| Admin 分派/转派 | PUT | `/tickets/{ticket_id}/assignee` | `TicketAssign` | `TicketDetailPublic` | 403、404、409 |
| Admin 取消分派 | DELETE | `/tickets/{ticket_id}/assignee` | — | `TicketDetailPublic` | 403、404、409 |
| Customer 回复 | POST | `/tickets/{ticket_id}/replies` | `CustomerReplyCreate` | `TicketMessagePublic`，201 | 403、404、409 closed |
| Staff 消息 | POST | `/tickets/{ticket_id}/messages` | `TicketMessageCreate` | `TicketMessagePublic`，201 | 403、404、409 closed |
| 修改状态 | PATCH | `/tickets/{ticket_id}/status` | `TicketStatusUpdate` | `TicketDetailPublic` | 403、404、409 非法流转 |
| 修改属性 | PATCH | `/tickets/{ticket_id}/attributes` | `TicketAttributesUpdate` | `TicketDetailPublic` | 403、404、409 closed |
| 删除工单 | DELETE | `/tickets/{ticket_id}` | `DeleteTicketRequest` body | 204 | 403、404、409 未确认 |
| 角色统计 | GET | `/tickets/statistics` | — | `TicketStatisticsPublic` | 401/403 |

`/tickets/statistics` 必须在 `/{ticket_id}` 之前注册，或使用明确 route order，避免将 `statistics` 解析为 UUID。

### 5.3 服务签名与路由映射

路由函数命名保持稳定，生成客户端按 tag `tickets` 和 `users` 生成 `TicketsService`、`UsersService`。每个路由显式指定 `operation_id`，避免函数重命名导致前端方法名漂移。

## 6. 错误处理策略

| 错误类型 | 错误码 | HTTP 状态 | 处理方式 |
|---|---|---:|---|
| 未认证或令牌无效 | `AUTH_REQUIRED` | 401 | 清除前端 token 并跳转登录 |
| 用户停用 | `USER_INACTIVE` | 403 | 拒绝所有业务请求 |
| 角色无权 | `ROLE_FORBIDDEN` | 403 | 不返回受保护资源内容 |
| 资源级无权 | `TICKET_FORBIDDEN` | 403 | 不返回标题、消息和负责人 |
| 工单不存在/已删除 | `TICKET_NOT_FOUND` | 404 | 统一视为不存在 |
| 用户不存在 | `USER_NOT_FOUND` | 404 | Admin 管理接口返回 |
| Email 重复 | `EMAIL_CONFLICT` | 409 | 保持原数据 |
| 工单已被接手 | `TICKET_ALREADY_CLAIMED` | 409 | 前端刷新列表、详情和统计 |
| 分派目标无效 | `INVALID_ASSIGNEE` | 409 | 仅允许活跃 Agent |
| 非法状态流转 | `INVALID_STATUS_TRANSITION` | 409 | 不修改任何字段、不写成功审计 |
| 工单已关闭 | `TICKET_CLOSED` | 409 | 页面切换只读状态 |
| 最后活跃 Admin | `LAST_ACTIVE_ADMIN` | 409 | 拒绝降级或停用 |
| 删除未确认 | `DELETE_CONFIRMATION_REQUIRED` | 409 | 不执行软删除 |
| 字段校验失败 | `VALIDATION_ERROR` | 422 | 返回字段路径和校验信息 |
| 未处理数据库错误 | `INTERNAL_ERROR` | 500 | 回滚并记录 request_id，不返回敏感 SQL |

FastAPI middleware 生成或透传 `X-Request-ID`，响应头和错误体都返回相同值。日志只记录角色、资源 ID、错误码和 request_id，不记录 JWT、密码、消息正文和内部备注正文。

## 7. 事务、并发与审计

### 7.1 事务规则

- 一个请求使用一个同步 SQLModel Session。
- Route 不执行 SQL、不调用 `commit()`。
- 每个 Service 写方法在一个事务中完成业务修改和审计插入。
- Repository 可以 `flush()` 或执行条件更新，但不 `commit()`。
- 失败路径回滚后不得留下消息、状态或审计的部分写入。
- 本期没有外部 HTTP 或模型调用，因此事务中不存在等待外部服务的问题。

### 7.2 原子接手

接手使用条件更新而非行读取后赋值：

```text
WHERE id = :ticket_id
  AND deleted_at IS NULL
  AND status = 'OPEN'
  AND assignee_id IS NULL
```

成功更新负责人、状态和更新时间后，在同一事务插入 `TAKEN` 审计。条件更新影响 0 行时，再读取工单区分 `404` 与 `409`；不能覆盖已有负责人。

### 7.3 最后活跃 Admin

当更新后的角色或启用状态会减少活跃 Admin 数量时：

1. 在事务内按用户 ID 固定顺序锁定全部活跃 Admin 行；
2. 计算更新后的活跃 Admin 数量；
3. 若小于 1，抛出 `LAST_ACTIVE_ADMIN`；
4. 否则完成更新并提交。

该规则必须通过两个独立数据库 Session 的并发测试验证，不能只测试 UI 禁用。

### 7.4 软删除和审计保留

Admin 删除时：

- 请求体必须为 `{"confirm": true}`；
- 工单必须未删除；
- 同事务写入 `DELETED` 审计并设置 `deleted_at`、`deleted_by_id`；
- 不提供恢复 API；
- 所有列表、详情、统计和授权查询默认过滤 `deleted_at IS NULL`；
- Message 与 AuditLog 保留在数据库中；
- API 对已删除 Ticket 返回 404。

## 8. 数据迁移设计

新增一个以当前 Alembic head `fe56fa70289e` 为前置的迁移：

`backend/app/alembic/versions/<revision>_replace_items_with_ticket_platform.py`

### Upgrade 顺序

1. 创建数据库枚举类型。
2. 给 `user` 添加 nullable `role`。
3. 将 `is_superuser=true` 回填为 `ADMIN`，其他回填为 `CUSTOMER`。
4. 检查至少存在一个 `is_active=true AND role='ADMIN'` 的用户；否则迁移失败。
5. 将 `role` 设为 NOT NULL，建立角色/状态索引。
6. 创建 `ticket`、`ticket_message`、`ticket_audit_log` 及索引。
7. 删除 `item` 表。
8. 删除 `user.is_superuser` 字段。

### Downgrade 顺序

1. 恢复 `user.is_superuser` 字段。
2. 将 `role='ADMIN'` 映射为 `is_superuser=true`，其他为 false。
3. 重建空的 `item` 示例表，不尝试从 Ticket 反向生成 Item。
4. 删除审计、消息和工单表及其索引。
5. 删除 `user.role` 和数据库枚举。

降级会丢弃 Ticket 数据，因此只用于开发环境或发布回滚前数据库备份恢复。生产回滚优先恢复发布前数据库快照，而不是执行破坏性 downgrade。

## 9. 前端路由与页面设计

### 9.1 路由结构

| 路径 | 允许角色 | 页面职责 |
|---|---|---|
| `/` | 全部 | 根据当前角色显示对应统计和快捷入口 |
| `/tickets` | Customer | 我的工单列表和创建入口 |
| `/tickets/$ticketId` | Customer | 自己工单的详情和公开回复 |
| `/queue` | Agent | 未分派、分派给我、等待客户 Tabs |
| `/queue/$ticketId` | Agent | 未分派或自己负责工单详情 |
| `/admin/tickets` | Admin | 全局工单管理 |
| `/admin/tickets/$ticketId` | Admin | 全局工单详情和管理动作 |
| `/admin/users` | Admin | 用户、角色和启停管理 |
| `/settings` | 全部 | 现有个人设置 |

不复用单一 `/tickets/$ticketId` 页面承担三种完全不同的路由权限。三个详情路由共享 `TicketDetailPage` 组件，但路由 guard、返回路径和允许操作由 role view 配置决定，避免页面内散布大量角色条件。

### 9.2 路由保护签名

```typescript
type UserRole = "CUSTOMER" | "AGENT" | "ADMIN"

type RequireRolesOptions = {
  allowed: readonly UserRole[]
  redirectTo: "/" | "/login"
}

function requireRoles(options: RequireRolesOptions): BeforeLoadFn
```

`requireRoles()` 通过 QueryClient 确保 `currentUser` 已加载。前端 guard 只负责用户体验；直接 API 请求仍由后端拒绝。

### 9.3 导航

| 角色 | 导航 |
|---|---|
| Customer | Dashboard、我的工单、设置 |
| Agent | Dashboard、客服队列、设置 |
| Admin | Dashboard、工单管理、用户管理、设置 |

侧栏根据 `currentUser.role` 从静态配置表生成，不在 JSX 中嵌套多个权限三元表达式。

## 10. 前端数据访问与缓存

### 10.1 Query Keys

```typescript
const ticketKeys = {
  all: ["tickets"] as const,
  lists: () => [...ticketKeys.all, "list"] as const,
  list: (scope: TicketScope, filters: TicketListFilters) => [...],
  details: () => [...ticketKeys.all, "detail"] as const,
  detail: (ticketId: string) => [...],
  statistics: () => [...ticketKeys.all, "statistics"] as const,
}

const userKeys = {
  current: ["currentUser"] as const,
  lists: () => ["users", "list"] as const,
  list: (filters: UserListFilters) => [...],
  agents: ["users", "agents"] as const,
}
```

查询键必须包含 page、pageSize、query、status、priority、category 和 assigneeId。对象字段按固定顺序规范化，避免语义相同筛选产生不同缓存键。

### 10.2 Mutation 失效规则

| Mutation | 必须失效的 Query |
|---|---|
| 创建工单 | Ticket lists、statistics |
| 接手 | Ticket lists、当前 detail、statistics |
| 分派/转派/取消分派 | Ticket lists、当前 detail、agents、statistics |
| 回复/内部备注 | 当前 detail、Ticket lists、statistics |
| 状态/优先级/分类 | 当前 detail、Ticket lists、statistics |
| 删除 | Ticket lists、当前 detail、statistics |
| 用户角色/状态更新 | User lists、agents、currentUser（目标为自己时） |

接手返回 `409 TICKET_ALREADY_CLAIMED` 时也失效当前 detail、lists 和 statistics，使页面显示真实负责人。

### 10.3 Auth 缓存

- 登录成功后先保存 token，再获取并缓存 `currentUser`，最后导航到 `/`。
- 登出时移除 token 并清空全部 QueryClient 缓存，防止下一个用户短暂看到前一用户数据。
- 全局 `401` 清除 token 和缓存后进入登录页。
- `403` 不统一退出登录，因为它仅表示当前用户无权访问该资源；页面展示错误或回到角色首页。

## 11. 服务端分页表格

扩展现有 `DataTable`，兼容服务端和现有简单表格：

```typescript
interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  pagination?: {
    pageIndex: number
    pageSize: number
    totalCount: number
    onPageChange: (pageIndex: number) => void
    onPageSizeChange: (pageSize: number) => void
  }
  toolbar?: ReactNode
  emptyState?: ReactNode
  isFetching?: boolean
}
```

提供 `pagination` 时启用 TanStack Table `manualPagination`，页数由 `totalCount` 计算；未提供时保留现有客户端分页行为。Ticket 和用户管理使用 URL search params 保存筛选与分页，刷新页面后条件不丢失，浏览器前进后退可恢复。

## 12. 前端组件设计

### 12.1 Ticket 组件

| 组件 | 职责 |
|---|---|
| `TicketFilters` | 关键字、状态、优先级、分类、负责人筛选；筛选变化重置到第 1 页 |
| `TicketColumns` | 编号、标题、状态、优先级、分类、创建人、负责人、更新时间和角色化操作 |
| `CreateTicketDialog` | Customer 创建标题、描述和分类；Zod 与后端约束一致 |
| `TicketDetailPage` | 装配 Header、Metadata、Timeline 和 ActionPanel |
| `TicketTimeline` | 展示后端已裁剪的公开回复、内部备注和公开审计事件 |
| `TicketReplyForm` | Customer 公开回复；Agent/Admin 公开回复或内部备注 Tabs |
| `TicketActionPanel` | 接手、状态、优先级和分类操作；Closed 时只读 |
| `TicketAssignmentDialog` | Admin 选择活跃 Agent，分派或转派 |
| `DeleteTicketDialog` | Admin 明确确认删除，不提供恢复入口 |
| `TicketStatistics` | 根据返回 Schema 展示角色计数卡片 |

Agent 浏览未分派工单时：

- 不显示内部备注；
- 不显示内部备注输入入口；
- 只显示“接手”动作；
- 接手成功后刷新详情，才显示负责 Agent 的回复、备注和状态操作。

### 12.2 用户管理组件

复用现有 Admin Dialog、Form、DataTable 和 toast 模式：

- `AddUser` 增加角色 Select 和启用状态；
- `EditUser` 将 `is_superuser` 替换为单角色 Select；
- `columns.tsx` 显示 Role Badge 和 Active 状态；
- 用户列表接入服务端筛选分页；
- 不显示物理删除操作；
- `LAST_ACTIVE_ADMIN` 以明确 toast 和表单错误展示。

### 12.3 表单校验

| 表单 | 前端校验 |
|---|---|
| 创建工单 | 标题 1～200；描述 1～10,000；分类必选 |
| 回复/备注 | 去除首尾空白后 1～10,000 |
| 用户创建 | 复用现有邮箱和密码规则；角色必选 |
| 用户修改 | 至少修改一个字段；角色使用固定枚举 |
| 删除工单 | 用户点击二次确认按钮后发送 `confirm=true` |

前端校验用于即时反馈，后端仍执行完整校验。

## 13. OpenAPI 生成流程

1. 后端模型、Schema、路由和测试完成。
2. 后端 OpenAPI 契约测试通过。
3. 执行现有 `scripts/generate-client.sh`。
4. 生成 `frontend/openapi.json` 和 `frontend/src/client/**`。
5. 前端只从生成客户端导入类型和 Service。
6. `routeTree.gen.ts` 由 TanStack Router 插件生成，不手工编辑。

不新增手写 `fetch`、Axios URL 或第二套 `src/api` 封装。

## 14. 测试设计

### 14.1 后端测试分层

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/services/test_ticket_permissions.py` | 三角色资源级权限和内部备注可见性纯逻辑 |
| `tests/services/test_ticket_state_machine.py` | 全部允许与拒绝的状态转换 |
| `tests/services/test_user_service.py` | 公开注册默认角色、启停、最后 Admin 保护 |
| `tests/repositories/test_ticket_repository.py` | 筛选分页、角色范围、软删除过滤、统计聚合 |
| `tests/repositories/test_ticket_concurrency.py` | 两独立 Session 原子接手和并发 Admin 不变量 |
| `tests/api/routes/test_tickets.py` | 创建、列表、详情、筛选、分页、属性和删除契约 |
| `tests/api/routes/test_ticket_messages.py` | 回复、备注、Customer/未分派 Agent 数据裁剪 |
| `tests/api/routes/test_ticket_assignment.py` | 接手、分派、转派、取消分派 |
| `tests/api/routes/test_ticket_statistics.py` | 三角色统计范围 |
| `tests/api/routes/test_users.py` | 三角色用户管理和现有个人能力回归 |
| `tests/test_openapi.py` | operation_id 唯一、错误响应和主要 Schema 存在 |
| `tests/migrations/test_ticket_platform_migration.py` | 老库升级、角色回填、Item 删除和降级保护 |

核心权限、状态机和校验采用 TDD。并发测试必须创建两个独立 Session/连接并同步执行，顺序 TestClient 请求不能替代并发验证。

### 14.2 测试 Fixtures

提供：

```python
@pytest.fixture
def customer_user(db: Session) -> User: ...
@pytest.fixture
def agent_user(db: Session) -> User: ...
@pytest.fixture
def second_agent_user(db: Session) -> User: ...
@pytest.fixture
def admin_user(db: Session) -> User: ...
@pytest.fixture
def customer_headers(...) -> dict[str, str]: ...
@pytest.fixture
def agent_headers(...) -> dict[str, str]: ...
@pytest.fixture
def admin_headers(...) -> dict[str, str]: ...
```

每个测试使用事务回滚或按外键依赖顺序清理 `ticket_audit_log → ticket_message → ticket → user`。测试不得依赖执行顺序。

### 14.3 前端 E2E

| 测试文件 | 核心流程 |
|---|---|
| `tickets-customer.spec.ts` | 注册、创建、筛选、详情、回复、跨用户拒绝、Closed 只读 |
| `tickets-agent.spec.ts` | 公共队列、接手、冲突刷新、公开回复、内部备注、等待和解决 |
| `tickets-admin.spec.ts` | 创建 Agent、分派、转派、取消分派、重开、关闭、删除和用户启停 |
| `role-navigation.spec.ts` | 三角色导航和直接输入无权路由 |
| `auth-regression.spec.ts` | 登录、登出缓存隔离、密码重置和个人设置 |

为 Customer、Agent、Admin 使用独立 BrowserContext 或 storage state。转派测试保留原 Agent 上下文，转派后验证原 Agent 详情请求和页面均不可访问。

## 15. 关键决策与理由

| 决策 | 可选方案 | 选择 | 理由 |
|---|---|---|---|
| 后端结构 | A: 延续路由直接 CRUD / B: service + repository 分层 | B | 状态机、审计和并发需要单一业务边界；路由直接 commit 无法保证原子性 |
| 部署形态 | A: 单体 / B: 微服务 | A | 业务规模和团队规模不需要分布式复杂度，单体最易测试和部署 |
| 角色模型 | A: 多角色关联表 / B: User 单枚举字段 | B | spec 明确每个用户只能一个角色，枚举字段更简单并避免无效组合 |
| Ticket 删除 | A: 物理删除并复制审计 / B: 不可恢复软删除 | B | 同时满足业务不可见、无恢复入口和审计/消息保留，外键最稳定 |
| 并发接手 | A: 先查再更新 / B: 条件 UPDATE | B | 单条条件更新由数据库保证原子性，可可靠返回一个成功一个冲突 |
| 最后 Admin | A: UI 禁用 / B: Service 检查 / C: 事务行锁 + 检查 | C | UI 和普通 count 均有并发竞态，锁定活跃 Admin 后检查满足数据库一致性 |
| 内部备注裁剪 | A: 前端隐藏 / B: 后端响应裁剪 | B | spec 要求不能泄露正文、类型、数量或存在信息，必须在数据出口裁剪 |
| 工单编号 | A: 额外自增序列 / B: `TKT-` + UUID | B | 全局唯一且不可变，不增加额外序列、锁和格式迁移 |
| 审计值 | A: 文本描述 / B: JSON 前后快照 | B | JSON 可稳定展示和测试，不依赖自然语言解析，也便于后续扩展 AI 前保留结构化事实 |
| API 更新方式 | A: 手写前端 API / B: OpenAPI 生成 | B | 项目已有生成链，复用可减少契约漂移 |
| 表格分页 | A: 客户端全量分页 / B: 扩展 DataTable 为受控服务端分页 | B | spec 要求筛选后总数和最大 100 条分页，不能拉取全量数据 |
| 详情路由 | A: 单路由大量角色分支 / B: 角色路由共享组件 | B | 路由权限清晰，同时复用详情组件，降低误显示无权操作的概率 |
| 状态存储 | A: 新增全局状态库 / B: Router URL + React Query | B | 现有栈已覆盖服务端状态和 URL 筛选，不需要 Redux/Zustand |
| 用户删除 | A: 保留物理删除 / B: 仅停用 | B | 用户历史身份必须保留，符合 spec 且避免审计外键断裂 |
| Item 退出 | A: 转换为 Ticket / B: 删除示例表与入口 | B | spec 明确不迁移示例数据，转换会制造无业务意义的工单 |

## 16. 风险与权衡

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| 用户角色迁移错误导致 Admin 无法登录 | 中 | 高 | 先回填角色并验证至少一个活跃 Admin，再删除旧字段；迁移测试覆盖历史数据 |
| 并发接手出现负责人覆盖 | 中 | 高 | 条件 UPDATE + 同事务审计；两独立连接并发测试 |
| 两个 Admin 并发降级破坏最后 Admin 不变量 | 低 | 高 | 锁定全部活跃 Admin 行并在锁内计算更新后数量 |
| Customer 或未分派 Agent 获得内部备注 | 中 | 高 | repository 查询参数 `include_internal` 由后端权限策略决定；API 序列化和 E2E 双重测试 |
| 软删除过滤遗漏导致已删工单重新出现 | 中 | 高 | 所有 Ticket 查询只通过 repository 的 active 查询入口；测试列表、详情、统计和搜索 |
| 路由 Service 仍直接提交造成部分事务 | 中 | 高 | 代码审查搜索 route 中 SQL/commit；Service 写方法拥有事务；失败注入测试 |
| OpenAPI 生成后前端大范围类型变化 | 高 | 中 | 后端契约测试通过后一次生成；禁止手工改生成文件；前端 build/typecheck 门控 |
| DataTable 扩展破坏现有 Admin 表格 | 中 | 中 | 保留无 `pagination` 参数时的客户端兼容模式；组件测试覆盖两种模式 |
| Item 表直接删除导致开发者误以为可恢复数据 | 低 | 中 | 发布前备份；迁移说明明确 Item 不迁移；生产回滚依赖快照 |
| 工单编号较长影响 UI | 中 | 低 | 列表使用等宽字体和截断/复制控件，完整值在详情显示；不牺牲唯一性 |
| 现有 localStorage Token 在角色变更后继续缓存旧页面 | 中 | 中 | 后端每请求读取最新 User；角色更新后失效 currentUser；403 页面回到角色首页 |

## 17. 发布策略

- **发布方式**：一次性后端数据库迁移和应用发布；前后端同版本发布。该项目当前是模板二次开发，不维护旧 Items 客户端并行窗口。
- **发布顺序**：数据库备份 → 停止旧应用写入 → 执行 Alembic upgrade → 验证活跃 Admin 和新表 → 发布后端 → 健康检查/OpenAPI 冒烟 → 发布前端 → 三角色冒烟。
- **回滚条件**：迁移失败、无活跃 Admin、登录失败率异常、Ticket 核心 API 5xx、内部备注越权、接手出现多个成功中的任一项。
- **数据迁移**：现有 Admin/Customer 角色映射必须在应用启动前完成；Item 数据不迁移。
- **回滚策略**：应用发布前创建数据库快照。若已产生 Ticket 生产数据，不执行破坏性 Alembic downgrade，恢复数据库快照并回滚应用镜像。
- **版本策略**：本期直接替换未对外承诺的模板 Item API；不保留 `/items` 兼容端点。前端和后端必须同时切换。
- **安全验证**：发布后使用 Customer、Agent、Admin 三账号验证数据范围，并专门验证内部备注不出现在 Customer 和未分派 Agent 响应中。

## 18. 变更文件清单

### 18.1 后端新增

| 文件路径 | 操作 | 变更说明 |
|---|---|---|
| `backend/app/models/__init__.py` | 新增 | 导出 ORM 模型和枚举，替代单文件模型入口 |
| `backend/app/models/user.py` | 新增 | User ORM 和 UserRole |
| `backend/app/models/ticket.py` | 新增 | Ticket、Message、Audit ORM 和枚举 |
| `backend/app/schemas/__init__.py` | 新增 | 导出 API Schema |
| `backend/app/schemas/common.py` | 新增 | Message、分页和错误响应 |
| `backend/app/schemas/auth.py` | 新增 | Token、密码重置 Schema |
| `backend/app/schemas/user.py` | 新增 | 用户请求响应和筛选 Schema |
| `backend/app/schemas/ticket.py` | 新增 | 工单请求响应、筛选和统计 Schema |
| `backend/app/core/errors.py` | 新增 | 领域错误、错误码和异常映射 |
| `backend/app/core/request_context.py` | 新增 | request_id middleware/context |
| `backend/app/repositories/user_repository.py` | 新增 | 用户查询、活跃 Agent 和 Admin 行锁 |
| `backend/app/repositories/ticket_repository.py` | 新增 | 角色化查询、条件接手、消息、审计和统计 |
| `backend/app/services/user_service.py` | 新增 | 用户角色与启停业务 |
| `backend/app/services/ticket_service.py` | 新增 | Ticket 生命周期和事务编排 |
| `backend/app/services/statistics_service.py` | 新增 | 角色统计 |
| `backend/app/api/routes/tickets.py` | 新增 | Ticket HTTP API |
| `backend/app/alembic/versions/<revision>_replace_items_with_ticket_platform.py` | 新增 | 角色回填、新表、Item 删除 |
| `backend/tests/services/test_ticket_permissions.py` | 新增 | 权限策略 TDD |
| `backend/tests/services/test_ticket_state_machine.py` | 新增 | 状态机 TDD |
| `backend/tests/services/test_user_service.py` | 新增 | 角色与最后 Admin |
| `backend/tests/repositories/test_ticket_repository.py` | 新增 | 查询与统计 |
| `backend/tests/repositories/test_ticket_concurrency.py` | 新增 | 并发不变量 |
| `backend/tests/api/routes/test_tickets.py` | 新增 | Ticket 契约 |
| `backend/tests/api/routes/test_ticket_messages.py` | 新增 | 消息与可见性 |
| `backend/tests/api/routes/test_ticket_assignment.py` | 新增 | 接手分派 |
| `backend/tests/api/routes/test_ticket_statistics.py` | 新增 | 统计契约 |
| `backend/tests/migrations/test_ticket_platform_migration.py` | 新增 | 迁移验证 |
| `backend/tests/utils/ticket.py` | 新增 | Ticket 测试工厂 |
| `backend/tests/test_openapi.py` | 新增 | OpenAPI 稳定性 |

### 18.2 后端修改/删除

| 文件路径 | 操作 | 变更说明 |
|---|---|---|
| `backend/app/models.py` | 删除 | 内容迁移到 `app/models` package |
| `backend/app/crud.py` | 修改 | 仅保留或迁移认证所需兼容入口，不承载 Ticket 业务 |
| `backend/app/api/deps.py` | 修改 | Admin 角色依赖和活跃用户行为 |
| `backend/app/api/main.py` | 修改 | 注册 Tickets，移除 Items |
| `backend/app/api/routes/users.py` | 修改 | 三角色用户管理，移除物理删除 |
| `backend/app/api/routes/login.py` | 修改 | 更新 Schema import 和 Admin 依赖名 |
| `backend/app/api/routes/items.py` | 删除 | Item API 退出 |
| `backend/app/core/db.py` | 修改 | 初始用户改为 ADMIN |
| `backend/app/main.py` | 修改 | request_id 和领域异常 handler |
| `backend/app/alembic/env.py` | 修改 | 从 models package 加载完整 metadata |
| `backend/tests/conftest.py` | 修改 | 三角色 fixtures 和数据隔离 |
| `backend/tests/api/routes/test_users.py` | 修改 | 三角色、启停和无物理删除测试 |
| `backend/tests/api/routes/test_login.py` | 修改 | 角色迁移和停用回归 |
| `backend/tests/api/routes/test_items.py` | 删除 | Item 测试退出 |
| `backend/tests/utils/item.py` | 删除 | Item 测试工厂退出 |

### 18.3 前端新增

| 文件路径 | 操作 | 变更说明 |
|---|---|---|
| `frontend/src/lib/routeGuards.ts` | 新增 | 角色路由保护 |
| `frontend/src/lib/ticketQueries.ts` | 新增 | Query keys 和 options |
| `frontend/src/components/ui/textarea.tsx` | 新增 | 长文本输入 |
| `frontend/src/components/Tickets/TicketFilters.tsx` | 新增 | 筛选工具栏 |
| `frontend/src/components/Tickets/TicketColumns.tsx` | 新增 | 工单列表列 |
| `frontend/src/components/Tickets/CreateTicketDialog.tsx` | 新增 | Customer 创建工单 |
| `frontend/src/components/Tickets/TicketDetailPage.tsx` | 新增 | 共享详情装配 |
| `frontend/src/components/Tickets/TicketTimeline.tsx` | 新增 | 消息和审计时间线 |
| `frontend/src/components/Tickets/TicketReplyForm.tsx` | 新增 | 回复和内部备注 |
| `frontend/src/components/Tickets/TicketActionPanel.tsx` | 新增 | 接手、状态和属性 |
| `frontend/src/components/Tickets/TicketAssignmentDialog.tsx` | 新增 | Admin 分派转派 |
| `frontend/src/components/Tickets/DeleteTicketDialog.tsx` | 新增 | Admin 删除确认 |
| `frontend/src/components/Tickets/TicketStatistics.tsx` | 新增 | 角色统计卡片 |
| `frontend/src/routes/_layout/tickets.tsx` | 新增 | Customer 列表 |
| `frontend/src/routes/_layout/tickets/$ticketId.tsx` | 新增 | Customer 详情 |
| `frontend/src/routes/_layout/queue.tsx` | 新增 | Agent 队列 |
| `frontend/src/routes/_layout/queue/$ticketId.tsx` | 新增 | Agent 详情 |
| `frontend/src/routes/_layout/admin/tickets.tsx` | 新增 | Admin 工单列表 |
| `frontend/src/routes/_layout/admin/tickets/$ticketId.tsx` | 新增 | Admin 工单详情 |
| `frontend/src/routes/_layout/admin/users.tsx` | 新增 | Admin 用户管理 |
| `frontend/tests/tickets-customer.spec.ts` | 新增 | Customer E2E |
| `frontend/tests/tickets-agent.spec.ts` | 新增 | Agent E2E |
| `frontend/tests/tickets-admin.spec.ts` | 新增 | Admin E2E |
| `frontend/tests/role-navigation.spec.ts` | 新增 | 路由权限 E2E |
| `frontend/tests/auth-regression.spec.ts` | 新增 | Auth 回归 |
| `frontend/tests/utils/roles.ts` | 新增 | 三角色测试 helper |

### 18.4 前端修改/删除/生成

| 文件路径 | 操作 | 变更说明 |
|---|---|---|
| `frontend/src/hooks/useAuth.ts` | 修改 | 登录刷新当前用户、登出清空缓存 |
| `frontend/src/main.tsx` | 修改 | 区分 401 和 403 全局行为 |
| `frontend/src/components/Common/DataTable.tsx` | 修改 | 受控服务端分页兼容模式 |
| `frontend/src/components/Sidebar/AppSidebar.tsx` | 修改 | 三角色导航 |
| `frontend/src/routes/_layout.tsx` | 修改 | 当前用户加载协调 |
| `frontend/src/routes/_layout/index.tsx` | 修改 | 角色统计 Dashboard |
| `frontend/src/routes/_layout/admin.tsx` | 删除 | 被 Admin 子路由结构替代 |
| `frontend/src/components/Admin/AddUser.tsx` | 修改 | 单角色和启用状态 |
| `frontend/src/components/Admin/EditUser.tsx` | 修改 | 单角色和最后 Admin 错误 |
| `frontend/src/components/Admin/columns.tsx` | 修改 | Role/Status 列和服务端分页 |
| `frontend/src/components/Admin/DeleteUser.tsx` | 删除 | 不再物理删除用户 |
| `frontend/src/components/Admin/UserActionsMenu.tsx` | 修改 | 移除删除，保留编辑/启停 |
| `frontend/src/routes/_layout/items.tsx` | 删除 | Item 页面退出 |
| `frontend/src/components/Items/` | 删除 | Item 组件退出 |
| `frontend/src/components/Pending/PendingItems.tsx` | 删除 | Item loading 退出 |
| `frontend/tests/items.spec.ts` | 删除 | Item E2E 退出 |
| `frontend/tests/admin.spec.ts` | 修改 | 拆分到新 Admin/角色测试或删除旧场景 |
| `frontend/openapi.json` | 生成 | 后端契约快照 |
| `frontend/src/client/**` | 生成 | Ticket/User 客户端 |
| `frontend/src/routeTree.gen.ts` | 生成 | 新文件路由树 |

## How

## 19. 任务拆分

> 门控：工程基线任务 D-P01～D-P04 全部通过后才执行 D-B01；后端任务 D-B01～D-B13 全部通过后才执行 D-F01；前端任务完成后进入联调。核心权限、状态机、并发和校验任务采用 TDD。

| 编号 | 任务名称 | 详细描述 | 关联设计章节 | 工作量（人天） |
|---|---|---|---|---:|
| D-P01 | 【工程审计】(全栈) 盘点目录与跟踪边界 | 检查 Git 状态、文件用途、引用关系和磁盘产物；形成保留、忽略和候选删除清单 | §18、Delta Spec | 0.5 |
| D-P02 | 【忽略规则】(全栈) 完善 Git 忽略配置 | 覆盖 IDE、虚拟环境、缓存、构建、测试、覆盖率、日志、临时和本地密钥，同时保留锁文件及规格文档 | Delta Spec | 0.5 |
| D-P03 | 【模板清理】(全栈) 清理无项目用途的模板自动化 | 只删除已确认绑定 FastAPI 上游组织、模板发布或项目管理且无本项目引用的文件 | §18、Delta Spec | 0.5 |
| D-P04 | 【基线验证】(全栈) 验证工程整理结果 | 执行 ignore、文本格式、Compose 配置和不改变业务数据的基础命令检查 | §17、Delta Spec | 0.5 |
| D-B01 | 【模型拆分】(后端) 建立模型与 Schema 包 | 拆分 User/Auth/Common Schema；定义角色和 Ticket 枚举；保持旧认证 import 可迁移 | §2、§3、§18 | 1.5 |
| D-B02 | 【工单模型】(后端) 建立 Ticket 持久化模型 | 添加 Ticket、Message、Audit ORM、关系、约束和索引 metadata | §2 | 1.5 |
| D-B03 | 【数据迁移】(后端) 编写角色与工单迁移 | 回填角色、验证活跃 Admin、创建新表、删除 Item，并验证 upgrade/downgrade | §8、§17 | 2 |
| D-B04 | 【错误基础】(后端) 建立统一领域错误与 request_id | 添加稳定错误码、异常 handler、请求 ID 和安全日志边界 | §4.1、§6 | 1 |
| D-B05 | 【用户仓储】(后端) 实现用户查询与 Admin 锁 | 完成用户筛选分页、活跃 Agent 查询、活跃 Admin 行锁接口 | §4.2、§7.3 | 1 |
| D-B06 | 【用户服务】(后端) 实现三角色用户管理 | TDD 完成注册默认 Customer、Admin 创建修改、停用和最后 Admin 保护 | §4.4、§5.1、§7.3 | 2 |
| D-B07 | 【工单仓储】(后端) 实现角色查询与条件接手 | 完成角色范围、筛选分页、软删除过滤、消息审计查询和条件 UPDATE | §4.3、§7 | 2 |
| D-B08 | 【权限状态机】(后端) 实现 Ticket 纯业务策略 | TDD 完成可见性、内部备注、写权限和全部状态转换规则 | §4.7、§7 | 1.5 |
| D-B09 | 【工单服务一】(后端) 实现创建查询与接手分派 | 完成创建、列表、详情、原子接手、Admin 分派转派和取消分派事务 | §4.5、§5.2、§7.2 | 2 |
| D-B10 | 【工单服务二】(后端) 实现消息状态与属性 | 完成 Customer 回复自动重开、Staff 消息、状态和属性修改、内部备注裁剪 | §4.5、§7.1 | 2 |
| D-B11 | 【审计删除】(后端) 实现审计和不可恢复软删除 | 所有成功动作同事务审计；Admin 确认删除；业务查询统一过滤 | §2.2、§7.4 | 1.5 |
| D-B12 | 【统计接口】(后端) 实现角色化统计 | Repository 聚合和 StatisticsService/API，保证先授权后统计 | §4.6、§5.2 | 1 |
| D-B13 | 【后端契约】(后端) 完成路由、测试和 OpenAPI 门控 | 注册用户/Ticket API，移除 Items，完成并发、迁移、权限、OpenAPI 和认证回归测试 | §5、§14.1、§18 | 2 |
| D-F01 | 【客户端生成】(前端) 更新 OpenAPI 客户端 | 后端门控通过后运行生成脚本，确认 User/Ticket 类型和 Service 无重复手写接口 | §13 | 0.5 |
| D-F02 | 【认证路由】(前端) 实现角色 guard 与缓存隔离 | 完成 currentUser 加载、登录后刷新、登出清缓存、401/403 行为和三角色路由 | §9、§10.3 | 1.5 |
| D-F03 | 【通用表格】(前端) 扩展服务端分页 DataTable | 增加受控分页、总数、工具栏、空状态和兼容客户端模式 | §11 | 1 |
| D-F04 | 【工单查询】(前端) 建立查询键和筛选组件 | 实现 URL 筛选、规范化 Query keys、TicketFilters 和失效规则 | §10、§12.1 | 1.5 |
| D-F05 | 【客户工单】(前端) 实现 Customer 列表与创建 | 完成我的工单、创建 Dialog、字段校验、分页筛选和空状态 | §9.1、§12 | 1.5 |
| D-F06 | 【客服队列】(前端) 实现 Agent 队列和接手 | 完成未分派/我的/等待客户 Tabs、接手、409 刷新和未分派只读规则 | §9.1、§10.2、§12.1 | 2 |
| D-F07 | 【工单详情】(前端) 实现共享详情和时间线 | 完成三角色详情路由、公开/内部时间线、回复与备注表单和 Closed 只读 | §9、§12.1 | 2 |
| D-F08 | 【工单操作】(前端) 实现状态属性与 Admin 分派 | 完成状态、优先级、分类、分派、转派、取消分派和删除确认 | §12.1 | 2 |
| D-F09 | 【用户管理】(前端) 升级三角色用户管理 | 服务端分页筛选、角色 Select、启停、活跃 Agent 和最后 Admin 错误反馈 | §12.2 | 1.5 |
| D-F10 | 【角色看板】(前端) 实现 Dashboard 与导航 | 三角色统计卡片、快捷入口和静态导航配置 | §9.3、§12.1 | 1 |
| D-F11 | 【前端测试】(前端) 完成角色化 E2E | 独立三角色上下文覆盖 Customer、Agent、Admin、越权和认证回归 | §14.3 | 2 |
| D-I01 | 【全栈联调】(全栈) 验证三角色业务闭环 | 创建→接手/分派→回复→等待→重开→解决→关闭→删除，验证转派后权限变化 | §5、§9、§14 | 1 |
| D-I02 | 【安全回归】(全栈) 验证隔离与并发不变量 | 验证 Customer/未分派 Agent 内部备注隔离、原子接手和最后 Admin | §6、§7、§16 | 1 |
| D-I03 | 【发布验收】(全栈) 执行完整质量门控 | 后端 lint/type/test、前端 build/lint/E2E、OpenAPI 生成一致性、Docker 冒烟和迁移演练 | §8、§13、§17 | 1 |
| **合计** |  |  |  | **42.5** |

### 19.1 任务依赖

```text
D-P01 → D-P02 → D-P03 → D-P04 → D-B01

D-B01 → D-B02 → D-B03
D-B01 → D-B04
D-B01 → D-B05 → D-B06
D-B02 → D-B07 → D-B08 → D-B09 → D-B10 → D-B11
D-B07 → D-B12
D-B03 + D-B04 + D-B06 + D-B11 + D-B12 → D-B13

D-B13 → D-F01 → D-F02
D-F02 → D-F03 → D-F04
D-F04 → D-F05 → D-F07
D-F04 → D-F06 → D-F07
D-F07 → D-F08
D-F01 + D-F02 + D-F03 → D-F09
D-F05 + D-F06 + D-F08 + D-F09 → D-F10 → D-F11

D-F11 → D-I01 → D-I02 → D-I03
```

## Verify

设计自检：

- [x] FR-01～FR-19 分别通过 §2～§14 的数据、服务、接口、页面和测试方案覆盖，并由 §19 的 D-B01～D-I03 任务追踪实施。
- [x] 所有关键技术决策均记录可选方案、选择和理由。
- [x] HTTP 接口包含方法、路径、入参、出参和主要错误。
- [x] Service、Repository 和权限策略已定义到公开方法签名级。
- [x] 用户角色迁移、Ticket 新表、索引、Item 删除和 downgrade 行为明确。
- [x] 任务拆分覆盖后端、前端、联调、安全回归和发布验收。
- [x] 单任务为 0.5～2 人天，总量与 S2 全栈需求匹配。
- [x] 文档未包含方法体、可执行 SQL 或业务实现代码。
- [x] 已按 Python FastAPI 最佳实践检查权限、事务、并发、迁移、错误、审计和测试风险。
- [x] 已按 OpenAPI 生成规范确保前端不维护第二套 API。
- [x] 设计发现的未分派内部备注歧义已通过 Delta Spec 修正，并同步 `SYSTEM-SPEC.md`。

## Impact

- 后端架构：从模板路由直连数据库升级为 S2 所需的 route/service/repository 分层。
- 用户模型：`is_superuser` 迁移为单枚举 `role`，用户物理删除退出产品行为。
- 数据库：新增 Ticket、Message、Audit 三表和索引，删除 Item 表，存在破坏性迁移。
- API：移除 Items 和用户删除端点，新增 Ticket、角色用户管理和统计端点。
- 前端：Items 页面与组件退出，新增三角色路由、服务端分页和 Ticket 工作台。
- 生成产物：OpenAPI 客户端和 TanStack route tree 在后端契约和路由文件稳定后重新生成。
- 测试：新增 Service、Repository、并发、迁移、API 和三角色 E2E 测试。
- 外部依赖：不新增运行时外部服务或前端状态库；沿用 PostgreSQL、FastAPI、React 和现有 Docker。
