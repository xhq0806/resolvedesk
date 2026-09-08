# 任务清单

> 来源：design.md
> 生成时间：2026-08-24
> 当前阶段：后端业务编码进行中

## 工程基线

- [x] 【工程审计】（全栈）盘点目录与跟踪边界
  - 目标：检查 Git 状态、文件用途、引用关系和本地产物，区分保留、忽略与候选删除项。
  - 涉及文件：项目根目录、`.github/`、`.gitignore`、`backend/.gitignore`、`frontend/.gitignore`
  - 预期结果：规格、锁文件、源码、测试和部署配置保持可跟踪，本地产物不进入 Git 状态。
- [x] 【忽略规则】（全栈）完善 Git 忽略配置 `-> depends: 【工程审计】`
  - 目标：覆盖 IDE、虚拟环境、缓存、构建、测试、覆盖率、日志、临时文件和本地密钥。
  - 涉及文件：`.gitignore`、`backend/.gitignore`、`frontend/.gitignore`
  - 预期结果：代表性本地文件被忽略，锁文件、规格文档、生成客户端和模板示例环境配置仍可跟踪。
- [x] 【模板清理】（全栈）清理无项目用途的模板自动化 `-> depends: 【忽略规则】`
  - 目标：删除仅服务 FastAPI 上游组织管理、模板发布或生成后处理且不参与本项目运行的文件。
  - 涉及文件：`.github/workflows/`、`.github/pr-submit.yml`、`hooks/post_gen_project.py`
  - 预期结果：本项目测试、检查、发布和部署流程保留，已删除文件不存在有效项目引用。
- [x] 【基线验证】（全栈）验证工程整理结果 `-> depends: 【模板清理】`
  - 目标：验证忽略边界、文本格式、Compose 配置、依赖锁和前端构建。
  - 涉及文件：工程基线全部变更文件
  - 预期结果：`git check-ignore`、`git diff --check`、`docker compose config --quiet`、`uv lock --check`、目标文档检查和前端构建通过。

## 后端实施

- [x] 【模型拆分】（后端）建立模型与 Schema 分层 `-> depends: 【基线验证】`
  - 目标：拆分 User、Auth、Common Schema，定义角色和 Ticket 枚举。
  - 涉及文件：`backend/app/models/`、`backend/app/schemas/`
  - 预期结果：模型与 API Schema 职责分离，旧认证调用可迁移。
- [x] 【工单模型】（后端）建立 Ticket 持久化模型 `-> depends: 【模型拆分】`
  - 目标：添加 Ticket、Message、Audit ORM、关系、约束和索引。
  - 涉及文件：`backend/app/models/ticket.py`
  - 预期结果：数据库 metadata 完整表达工单领域。
- [x] 【数据迁移】（后端）编写角色与工单迁移 `-> depends: 【工单模型】`
  - 目标：回填角色、验证活跃 Admin、创建新表并删除 Item。
  - 涉及文件：`backend/app/alembic/versions/`、迁移测试
  - 预期结果：老库可升级，角色与历史账号保持有效。
- [x] 【错误基础】（后端）建立统一领域错误与 `request_id` `-> depends: 【模型拆分】`
  - 目标：添加稳定错误码、异常映射、请求 ID 和安全日志边界。
  - 涉及文件：`backend/app/core/errors.py`、`backend/app/core/request_context.py`、`backend/app/main.py`
  - 预期结果：业务错误返回稳定 `code`、`message` 和 `request_id`。
- [x] 【用户仓储】（后端）实现用户查询与 Admin 锁 `-> depends: 【模型拆分】`
  - 目标：完成用户筛选分页、活跃 Agent 查询和活跃 Admin 行锁。
  - 涉及文件：`backend/app/repositories/user_repository.py`
  - 预期结果：用户服务拥有安全的数据访问边界。
- [x] 【用户服务】（后端）实现三角色用户管理 `-> depends: 【用户仓储】`
  - 目标：TDD 完成注册默认 Customer、Admin 创建修改、停用和最后 Admin 保护。
  - 涉及文件：`backend/app/services/user_service.py`、用户测试
  - 预期结果：三角色和用户生命周期满足 spec。
- [x] 【工单仓储】（后端）实现角色查询与条件接手 `-> depends: 【工单模型】`
  - 目标：完成角色范围、筛选分页、软删除过滤、消息审计查询和原子条件更新。
  - 涉及文件：`backend/app/repositories/ticket_repository.py`
  - 预期结果：并发接手最多一个成功，所有查询遵守数据权限。
- [x] 【权限状态机】（后端）实现 Ticket 纯业务策略 `-> depends: 【工单仓储】`
  - 目标：TDD 完成可见性、内部备注、写权限和状态转换规则。
  - 涉及文件：`backend/app/services/`、权限和状态机测试
  - 预期结果：核心规则可独立测试且无 HTTP/数据库耦合。
- [x] 【工单服务一】（后端）实现创建查询与接手分派 `-> depends: 【权限状态机】`
  - 目标：完成创建、列表、详情、原子接手和 Admin 分派事务。
  - 涉及文件：`backend/app/services/ticket_service.py`
  - 预期结果：工单基础流程和负责人变更原子完成。
- [x] 【工单服务二】（后端）实现消息状态与属性 `-> depends: 【工单服务一】`
  - 目标：完成回复自动重开、Staff 消息、状态、属性和内部备注裁剪。
  - 涉及文件：`backend/app/services/ticket_service.py`
  - 预期结果：消息与状态机形成完整处理闭环。
- [x] 【审计删除】（后端）实现审计和不可恢复软删除 `-> depends: 【工单服务二】`
  - 目标：成功动作同事务审计，Admin 确认删除，业务查询统一过滤。
  - 涉及文件：Ticket service、repository、审计测试
  - 预期结果：删除后业务不可见且审计链保留。
- [x] 【统计接口】（后端）实现角色化统计 `-> depends: 【工单仓储】`
  - 目标：按角色授权范围完成数据库聚合和统计响应。
  - 涉及文件：`backend/app/services/statistics_service.py`、Ticket repository
  - 预期结果：三角色统计不发生跨权限泄漏。
- [x] 【后端契约】（后端）完成路由、测试和 OpenAPI 门控
  - 目标：注册用户和 Ticket API，移除 Items，完成并发、迁移、权限和认证回归测试。
  - 涉及文件：`backend/app/api/`、`backend/tests/`
  - 预期结果：后端 lint、类型、测试和 OpenAPI 契约全部通过。

## 前端实施

- [x] 【后端契约】（前端）完成路由、测试和 OpenAPI 门控
  - 目标：从稳定后端契约生成 User 和 Ticket 客户端。
  - 涉及文件：`frontend/openapi.json`、`frontend/src/client/`
  - 预期结果：前端无第二套手写业务 API。
- [x] 【认证路由】（前端）实现角色 guard 与缓存隔离 `-> depends: 【客户端生成】`
  - 目标：完成 currentUser 加载、登录刷新、登出清缓存和三角色路由保护。
  - 涉及文件：`frontend/src/hooks/useAuth.ts`、路由和 guard
  - 预期结果：角色导航和路由体验正确，缓存不跨账号泄漏。
- [x] 【通用表格】（前端）扩展服务端分页 DataTable `-> depends: 【认证路由】`
  - 目标：增加受控分页、总数、工具栏、空状态和兼容模式。
  - 涉及文件：`frontend/src/components/Common/DataTable.tsx`
  - 预期结果：Ticket 和用户列表可使用服务端分页。
- [x] 【工单查询】（前端）建立查询键和筛选组件 `-> depends: 【通用表格】`
  - 目标：实现 URL 筛选、规范化 Query keys 和缓存失效规则。
  - 涉及文件：`frontend/src/lib/ticketQueries.ts`、Ticket filters
  - 预期结果：筛选、分页和浏览器导航状态稳定。
- [x] 【客户工单】（前端）实现 Customer 列表与创建 `-> depends: 【工单查询】`
  - 目标：完成我的工单、创建表单、筛选分页和空状态。
  - 涉及文件：Customer Ticket 路由与组件
  - 预期结果：Customer 可以完成工单创建与查询。
- [x] 【客服队列】（前端）实现 Agent 队列和接手 `-> depends: 【工单查询】`
  - 目标：完成公共队列、我的工单、等待客户、接手和冲突刷新。
  - 涉及文件：Agent Queue 路由与组件
  - 预期结果：Agent 只能访问未分派或自己负责的工单。
- [x] 【工单详情】（前端）实现共享详情和时间线
  - 目标：完成三角色详情、公开/内部时间线、回复表单和关闭只读。
  - 涉及文件：Ticket detail、timeline、reply components
  - 预期结果：后端裁剪结果按角色正确展示。
- [x] 【工单操作】（前端）实现状态属性与 Admin 分派 `-> depends: 【工单详情】`
  - 目标：完成状态、优先级、分类、分派、转派、取消分派和删除确认。
  - 涉及文件：Ticket action、assignment、delete components
  - 预期结果：各角色只看到并执行允许操作。
- [x] 【用户管理】（前端）升级三角色用户管理
  - 目标：实现服务端分页筛选、角色修改、启停和最后 Admin 错误反馈。
  - 涉及文件：`frontend/src/components/Admin/`、Admin user route
  - 预期结果：Admin 用户管理与后端契约一致。
- [x] 【角色看板】（前端）实现 Dashboard 与导航
  - 目标：展示三角色统计卡片、快捷入口和角色导航。
  - 涉及文件：Dashboard、Sidebar
  - 预期结果：每个角色进入匹配的工作台。
- [ ] 【前端测试】（前端）完成角色化 E2E
  - 目标：使用独立三角色上下文覆盖关键流程、越权和认证回归。
  - 涉及文件：`frontend/tests/`
  - 预期结果：前端 build、lint 和 E2E 通过。

## 联调与验收

- [ ] 【全栈联调】（全栈）验证三角色业务闭环 `-> depends: 【前端测试】`
  - 目标：验证创建、接手或分派、回复、等待、重开、解决、关闭和删除。
  - 涉及文件：全栈业务入口
  - 预期结果：三角色完整流程可重复执行。
- [ ] 【安全回归】（全栈）验证隔离与并发不变量 `-> depends: 【全栈联调】`
  - 目标：验证内部备注隔离、原子接手和最后活跃 Admin。
  - 涉及文件：后端安全测试、前端 E2E
  - 预期结果：关键权限和并发不变量通过。
- [ ] 【发布验收】（全栈）执行完整质量门控 `-> depends: 【安全回归】`
  - 目标：执行后端、前端、OpenAPI、Docker 和迁移演练。
  - 涉及文件：全部项目文件及运行配置
  - 预期结果：满足 reviewing 和 verify 的入口条件。

## 完成状态

> 进度：27/31 已完成
