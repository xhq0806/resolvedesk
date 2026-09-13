# 任务清单

> 来源: design.md
> 生成时间: 2026-09-11
> 当前阶段: 后端与前端纵向实现

## 实施任务

- [x] 【迁移基础】(后端) 建立 pgvector 与 Workspace 数据迁移
  - 目标: 添加 pgvector、Workspace/member/invitation 和 AI 基础持久化结构；把一期用户、工单、消息和审计回填到默认 Workspace。
  - 涉及文件: `backend/app/models/`, `backend/app/alembic/versions/`, `backend/tests/migrations/`, `compose.yml`, `compose.override.yml`
  - 预期结果: 迁移可重复执行，默认 Workspace 存在且至少有活跃 Owner/Admin，向量列与索引可用。
- [x] 【租户上下文】(后端) 实现 header 解析与成员策略 `← depends: 【迁移基础】`
  - 目标: 实现当前 Workspace 解析、成员邀请/切换/Owner 保护和跨租户统一错误。
  - 涉及文件: `backend/app/core/workspace.py`, `backend/app/repositories/workspace_repository.py`, `backend/app/services/workspace_service.py`, `backend/app/api/routes/workspaces.py`
  - 预期结果: 所有受保护请求按 WorkspaceContext 执行，非成员不能读取资源。
- [x] 【工单隔离】(后端) 迁移 Ticket 查询和一期 API `← depends: 【租户上下文】`
  - 目标: 为 Ticket/Message/Audit 查询、统计、状态机和 API 增加 Workspace 条件并保持一期行为。
  - 涉及文件: `backend/app/models/ticket.py`, `backend/app/repositories/ticket_repository.py`, `backend/app/services/ticket_service.py`, `backend/app/api/routes/tickets.py`, `backend/tests/`
  - 预期结果: 跨租户工单、消息、审计和统计均无数据泄漏，一期测试回归通过。
- [x] 【租户客户端】(前端) 实现 Workspace 切换和成员管理 `← depends: 【工单隔离】`
  - 目标: 增加 Workspace header 注入、切换器、邀请/角色管理和切换后的缓存清理。
  - 涉及文件: `frontend/src/lib/workspaceQueries.ts`, `frontend/src/components/Workspace/`, `frontend/src/routes/`, `frontend/src/client/`
  - 预期结果: 用户可切换 Workspace，前端不展示上一租户缓存。
- [x] 【Provider】(后端) 实现配置加密与 OpenAI-compatible adapter `← depends: 【迁移基础】`
  - 目标: 实现 Chat/Embedding 配置、API Key 加密脱敏、连接测试和 provider 错误映射。
  - 涉及文件: `backend/app/providers/`, `backend/app/services/provider_service.py`, `backend/app/models/ai.py`, `backend/app/api/routes/ai.py`, `backend/tests/`
  - 预期结果: 可配置 provider/base URL/模型，密钥不回显，外部失败进入稳定错误状态。
- [x] 【Provider UI】(前端) 实现模型和工具权限配置 `← depends: 【Provider】`
  - 目标: 实现 provider 表单、连接测试、工具逐项启停和权限反馈。
  - 涉及文件: `frontend/src/components/AI/`, `frontend/src/routes/_layout/ai.tsx`, `frontend/src/client/`
  - 预期结果: Owner/Admin 可配置和启停 AI 能力，前端看不到密钥原文。
- [x] 【知识入库】(后端) 实现文档任务、解析、切块和向量写入 `← depends: 【Provider】`
  - 目标: 实现文档安全校验、持久任务、解析/切块、Embedding 和 pgvector 写入。
  - 涉及文件: `backend/app/models/knowledge.py`, `backend/app/services/knowledge_service.py`, `backend/app/workers/knowledge_ingestion.py`, `backend/app/api/routes/knowledge.py`, `backend/tests/`
  - 预期结果: 文档可进入 PROCESSING/READY/FAILED，失败可重试，READY chunk 带来源元数据。
- [x] 【知识检索】(后端) 实现 Workspace 检索和来源裁剪 `← depends: 【知识入库】`
  - 目标: 按 Workspace 与 READY 状态执行向量检索，返回可定位来源并支持无依据拒答。
  - 涉及文件: `backend/app/repositories/knowledge_repository.py`, `backend/app/services/knowledge_service.py`, `backend/tests/`
  - 预期结果: 检索只返回当前租户文档，结果最多 5 个来源且可定位。
- [x] 【知识库 UI】(前端) 实现文档管理和引用 `← depends: 【知识检索】`
  - 目标: 实现文档上传、状态、重试、删除和来源定位。
  - 涉及文件: `frontend/src/components/Knowledge/`, `frontend/src/routes/_layout/knowledge.tsx`, `frontend/src/client/`
  - 预期结果: 文档管理和 RAG 来源可视化可用。
- [x] 【Agent 编排】(后端) 实现会话、SSE run 和取消接管 `← depends: 【知识检索】`
  - 目标: 实现会话、消息、run/event 生命周期、SSE、幂等、断流、取消和人工接管。
  - 涉及文件: `backend/app/services/agent_service.py`, `backend/app/models/ai.py`, `backend/app/api/routes/ai.py`, `backend/tests/`
  - 预期结果: 同一会话最多一个运行，流式失败/取消不生成半条 AI 回复。
- [x] 【工具执行】(后端) 实现 AI Agent 白名单与工单动作 `← depends: 【Agent 编排】`
  - 目标: 实现 Agent 实体、工具注册、授权、绑定工单校验、一期状态机重验和审计。
  - 涉及文件: `backend/app/services/tool_executor.py`, `backend/app/models/ai.py`, `backend/app/services/ticket_service.py`, `backend/tests/`
  - 预期结果: AI 只能执行已授权工具，不操作未绑定工单或破坏性资源。
- [x] 【AI 工作台】(前端) 实现流式聊天和工具状态 `← depends: 【工具执行】`
  - 目标: 实现 delta、来源、工具事件、取消、接管/恢复和工单上下文 UI。
  - 涉及文件: `frontend/src/components/AI/`, `frontend/src/routes/_layout/ai.tsx`, `frontend/src/client/`
  - 预期结果: 客户可完成 AI 对话并看到 AI 身份、来源和工具状态。
- [x] 【附件】(全栈) 实现文件安全和资源关联 `← depends: 【租户上下文】`
  - 目标: 实现附件类型/magic/大小校验、隔离存储、授权下载、删除审计和界面。
  - 涉及文件: `backend/app/models/attachment.py`, `backend/app/services/attachment_service.py`, `backend/app/api/routes/attachments.py`, `frontend/src/components/Attachments/`, `backend/tests/`
  - 预期结果: 工单和会话附件可安全上传、下载和删除。
- [x] 【测试验收】(全栈) 完成安全、RAG、Agent 和演示回归 `← depends: 【AI 工作台】`
  - 目标: 覆盖迁移、多租户、Provider、RAG、Tool、SSE、附件失败路径和主链路 E2E。
  - 涉及文件: `backend/tests/`, `frontend/tests/`, `compose.yml`, `README.md`
  - 预期结果: 自动化测试、类型检查、OpenAPI、前端构建、Playwright 和 Docker 健康检查通过。

## 完成状态

> 进度: 14/14 已完成
> 当前实现进展：后端已完成 Workspace/成员上下文、Ticket 多租户隔离、Provider 加密与 OpenAI-compatible Chat/Embedding、知识文档上传/解析/切块/Embedding 摄取、pgvector 迁移、Workspace 隔离检索、AI 会话/SSE Run 生命周期、人工接管/取消/恢复、工具白名单和服务端工单动作重验、附件安全校验/隔离存储/授权下载删除；前端已加入 Workspace 切换与缓存清理、Provider/工具权限、知识库上传状态和 AI SSE 工作台。迁移、模型、Provider/知识/Agent/附件及核心回归共 130 个测试通过，后端 ruff/mypy/compileall、OpenAPI 路由检查和前端 TypeScript/Vite 构建通过；全量测试仍有 13 个一期账号接口的英文/中文文案基线断言不一致，未纳入本期功能缺陷。
