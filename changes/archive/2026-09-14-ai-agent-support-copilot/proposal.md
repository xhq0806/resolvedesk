> 来源：用户需求描述
> 生成时间：2026-09-14
> 阶段：proposal

### Why（意图）

现有 AI/RAG 能力更像后台工作台：Customer/Agent 仍可看到知识库入口，Customer 缺少前台在线咨询体验。需要把知识库收敛为 Admin 管理能力，并让客户通过悬浮“在线咨询”与 AI Agent 交互、必要时转人工生成工单。

### What（范围）

#### 做什么

- [ ] 知识库仅 Admin/Owner 可见可管，Agent/Customer 侧边栏不显示入口。
- [ ] Customer 右下角提供“在线咨询”悬浮入口，打开 AI 对话面板。
- [ ] AI Agent 基于当前 Workspace 知识库回答，并支持客户请求转人工。
- [ ] 转人工时创建工单，优先自动分派给可用 Agent，否则进入未分派队列。

#### 不做什么

- [ ] 不做复杂排班、客服组长、SLA、计费和跨 Workspace 知识共享。
- [ ] 不开放 Agent/Customer 直接浏览或管理知识库。

### 初步技术方向

沿用现有 Workspace、RAG、AI conversation、ticket 状态机和权限模型；前端新增 Customer 浮窗入口，后端补齐转人工创建/分派工单契约。

### 成功标准

- [ ] Customer/Agent 无知识库导航和直达权限，Admin 可正常管理知识库。
- [ ] Customer 可从悬浮入口完成 AI 咨询、查看回答和发起转人工。
- [ ] 转人工生成工单并按可用客服分派；无人可用时进入公共队列。
