# Customer 在线咨询发送按钮与 Enter 发送排查记录

> 时间：2026-09-14
> 类型：前端交互细节修复

## 排查步骤

- [x] 阅读 `frontend/src/components/AI/CustomerSupportWidget.tsx`
- [x] 定位输入区按钮实现
- [x] 检查 Textarea 是否绑定键盘发送事件
- [x] 修改发送按钮尺寸和文案
- [x] 增加 Enter 发送、Shift+Enter 换行
- [x] 运行前端构建并重建 Docker backend 静态产物

## 假设与验证

| 假设 | 置信度 | 验证结果 |
|---|---:|---|
| 发送按钮太小是因为使用了 icon 尺寸 | 高 | 代码中按钮使用 `size="icon"`，固定为小方形 |
| Enter 不发送是因为 Textarea 未监听键盘事件 | 高 | Textarea 只有 `onChange`，没有 `onKeyDown` |
| 需要后端接口修改 | 低 | 问题发生在消息提交前的输入控件交互 |

## 根因链路

1. 在线咨询面板底部使用 Textarea + Button。
2. Button 使用 `size="icon"`，视觉上只适合纯图标按钮，放在输入区右侧显得过小。
3. Textarea 默认 Enter 行为是换行；组件没有自定义 `onKeyDown`。
4. 因此用户只能点击小按钮发送，不能按 Enter 发送。

## 修复方案

- 将发送按钮改为 `h-20 min-w-20 px-4`，同时显示发送图标和“发送”文字。
- 为 Textarea 增加 `onKeyDown`：
  - Enter：阻止默认换行并发送；
  - Shift+Enter：保留多行输入；
  - 输入法组合态 `isComposing`：不触发送，避免中文输入未完成时误发。

## 验证结果

- `bun run build` 通过。
- `docker compose -f compose.yml -f compose.override.yml up -d --build backend` 成功。
- 后端健康检查 `GET /api/v1/utils/health-check/` 返回 200。
- `git diff --check` 通过，仅有 CRLF 提示。
