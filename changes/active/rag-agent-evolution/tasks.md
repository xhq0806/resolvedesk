# 任务清单

> 来源：design.md
>
> 生成时间：2026-09-19

## 实施任务

- [x] 【策略与追踪模型】(后端) 新增持久化模型和迁移
  - 目标: 为每个 Workspace 保存 trace 开关，并持久化无正文的检索 trace。
  - 涉及文件: `backend/app/models/knowledge.py`, `backend/app/models/__init__.py`, `backend/app/alembic/versions/*_add_rag_retrieval_traces.py`
  - 预期结果: 迁移后策略与 trace 表、唯一约束和时间索引可用。
- [x] 【检索追踪】(后端) 在现有检索服务中记录 trace
  - 目标: Dense Retrieval 不变，开启策略时写入 HMAC 指纹和候选元数据。
  - 涉及文件: `backend/app/repositories/knowledge_repository.py`, `backend/app/services/knowledge_retrieval.py`, `backend/app/services/agent_service.py`
  - 预期结果: Customer 与管理端搜索均可关联 request/conversation，追踪失败不影响回答。
- [x] 【管理契约】(后端) 提供策略和 trace API
  - 目标: 仅管理者可启停策略并查看当前 Workspace 的追踪记录。
  - 涉及文件: `backend/app/schemas/knowledge.py`, `backend/app/api/routes/knowledge.py`
  - 预期结果: OpenAPI 暴露稳定的 GET/PATCH 策略与 GET trace 契约。
- [x] 【检索回归】(后端) 覆盖追踪、权限和隔离
  - 目标: 覆盖关闭开关、HMAC 脱敏、Workspace 隔离、管理权限和 API 契约。
  - 涉及文件: `backend/tests/services/test_knowledge_retrieval.py`, `backend/tests/api/routes/test_knowledge.py`
  - 预期结果: 相关 pytest、ruff、mypy 和 OpenAPI 检查通过。

## 完成状态

> 进度: 4/4 已完成。
