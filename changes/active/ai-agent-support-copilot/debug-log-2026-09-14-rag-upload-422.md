# RAG 文档上传 422 排查记录

日期：2026-09-14  
范围：`POST /api/v1/workspaces/{workspace_id}/knowledge/documents`

## 排查步骤

- 检查前端 `KnowledgePanel` 与 `aiApi.ts`：确认使用 multipart `FormData`，字段名为 `file`，Workspace header 与 URL 一致。
- 检查后端 `knowledge.py`：确认路由只在 Workspace 校验和 `KnowledgeService.create_document` 处可能返回领域校验错误。
- 检查 `knowledge_service.py`：确认 422 的直接来源是文件名、扩展名、大小和 MIME 严格校验。
- 对照浏览器行为分析：Windows 浏览器对 Markdown、DOCX 可能发送 `text/plain`、`application/octet-stream` 或空 MIME，而旧逻辑只接受单一标准 MIME。
- 使用真实 `README.md` 调用线上 Docker 服务：MIME 校验通过后暴露数据库外键错误，确认 `document_ingestion_job` 可能先于 `knowledge_document` 插入。

## 假设与验证

| 假设 | 结果 |
|---|---|
| Workspace UUID 不存在 | 排除：该 UUID 已在数据库中确认存在；资源不存在通常返回 404。 |
| 当前用户权限不足 | 低可能：权限不足应返回 403，而非 422。 |
| 文件超限/为空 | 仍需在具体文件上确认，但属于正常校验反馈。 |
| 浏览器 MIME 与扩展名不完全一致 | 高置信度：旧逻辑会将合法 `.md/.docx/.pdf` 的常见 MIME 变体拒绝为 422。 |
| 摄取任务插入顺序不稳定 | 已验证：真实请求在 MIME 放宽后触发 `document_ingestion_job_document_id_fkey`，表现为 500。 |

## 根因定位链

浏览器选择合法文档 → multipart 上传携带浏览器推断的 MIME → 旧后端严格 MIME 校验可能返回 422；即使 MIME 通过，文档和任务无 ORM relationship 导致 SQLAlchemy 插入顺序不稳定 → 摄取任务先插入触发外键错误 → 500。

## 修复方案

- 后端按扩展名保留类型白名单，同时允许常见浏览器 MIME 变体（包括 `application/octet-stream`、Markdown 的 `text/plain`）。
- 在创建摄取任务前显式 `session.flush()` 文档，确保外键依赖已落库。
- 前端上传失败时解析后端 `message/detail`，并显示可操作错误，不再表现为“无反应”。
- 增加 MIME 兼容性回归测试。

## 验证状态

- `backend/tests/services/test_knowledge_service.py`：12 passed。
- `backend/app` compileall：通过。
- `frontend` `bun run build`：通过。
- Docker backend 重建并重启：通过。
- 使用真实 `README.md` 通过 `localhost:8000` 上传：返回 `201`，状态为 `PROCESSING`；随后清理了验证产生的测试文档。
- 测试 fixture 清理了本机开发库种子数据，已重新执行初始化并恢复原 Workspace UUID `a22919bc-ce0e-4b34-ac67-e281b4a4df5f`；登录和 Workspace 列表已确认正常。
- 发现数据库恢复期间旧 Workspace UUID 可能残留在浏览器 `localStorage`，已在受保护路由守卫中增加租户 ID 自动校正，避免工作台和工单查询先于侧栏切换器发出失效请求。
