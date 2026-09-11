# 为 ResolveDesk 做贡献

感谢你帮助改进 ResolveDesk。

## 修改代码前

请先阅读 [系统行为规格](./SYSTEM-SPEC.md) 和 [开发指南](./development.md)。如果变更会影响工单行为、角色、权限、状态流转、迁移或 API 契约，也请阅读 `changes/active/ai-customer-support-platform/` 下的当前材料。

请牢记当前产品边界：ResolveDesk 是一个单工作空间的人工客服支持平台。AI Copilot、多租户、实时聊天、附件、SLA 自动化和知识库等能力，需要单独完成产品决策后再实现。

## 开发

请按照 [development.md](./development.md) 搭建本地环境。发起 pull request 前，请运行与本次变更相关的检查：

```bash
uv run prek run --all-files
```

后端变更应包含聚焦的 Pytest 覆盖。前端变更应包含相关的 Playwright 或组件覆盖。API 变更必须重新生成 OpenAPI 客户端。

## Pull Request

Pull request 应保持聚焦，并说明：

1. 发生变化的用户可见行为或运维行为。
2. 受影响的文件和边界。
3. 已运行的测试和检查。
4. 是否涉及迁移、配置或部署影响。

不要提交密钥、本地虚拟环境、构建产物、覆盖率报告或生成日志。如果变更涉及 `uv.lock`、`bun.lock`、迁移或生成的 API 客户端，请保持它们同步。

## 自动化工具和 AI

欢迎使用自动化工具和 AI 助手来支持严谨的工程工作。不过，贡献仍然需要人工审查、清晰上下文、有意义的测试，以及对最终变更负责。

## 许可证

提交贡献即表示你同意你的贡献按照项目的 MIT 许可证授权。
