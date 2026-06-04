---
status: backlog
---

# Epic 7: 部署上线与全链路可观测

本 Phase 将 Personal Assistant 部署到 AgentArts Runtime 生产环境，配置全链路可观测性，并完成多渠道接入的最终验证。

---

## 背景

前 6 个 Phase 完成了所有核心功能。本 Phase 将其从本地开发环境推送到生产环境，确保稳定运行，并具备排障能力。

## 范围

- 生产环境 `agentarts launch` 部署
- OTEL 可观测性配置（Tracing / Logging / Metrics）
- 飞书渠道接入验证
- OfficeClaw 渠道接入验证
- 冒烟测试 + 稳定性验证
- 文档完善

## 不涉及

- CI/CD 流水线自动化（后续迭代，见 `architecture/devops/cicd.md`）
- 性能优化和容量规划

## 任务拆解

### 7.1 生产部署

- [ ] 确认 `agentarts_config.yaml` 生产配置
  - 更新 `base_image`、SWR 仓库、环境变量为生产值
  - 确认 `network_mode`（PUBLIC 或 PRIVATE + VPC）
- [ ] 执行 `agentarts launch`
- [ ] 验证 `/ping` 健康检查
- [ ] 验证 `/invocations` 正常响应

### 7.2 可观测性

- [ ] 确认 `agentarts_config.yaml` 中 `observability` 配置
  - tracing: enabled
  - metrics: enabled
  - logs: enabled
- [ ] 在 AgentArts 控制台查看 Trace 链路（一次完整对话的 agent → tools → finalize）
- [ ] 确认 Metrics 面板可查看请求量、延迟、错误率
- [ ] 确认 Logs 可搜索

### 7.3 飞书渠道接入

- [ ] 创建飞书 Bot（飞书开放平台）
- [ ] 配置事件回调 URL → `https://<runtime-domain>/feishu/webhook`
- [ ] 验证 URL 验证（Challenge）通过
- [ ] 飞书客户端 @Bot 发消息 → Agent 正常回复
- [ ] 用户身份映射（飞书 user_id → PA user_id）

### 7.4 OfficeClaw 渠道接入

- [ ] 在 Windows PC 安装并配置 OfficeClaw
- [ ] 配置 OfficeClaw 连接 AgentArts
- [ ] 验证飞书/微信通过 OfficeClaw 调用 Agent 正常

### 7.5 跨渠道 Memory 验证

- [ ] Web Chat 创建用户偏好
- [ ] 飞书渠道发起对话 → Agent 加载相同偏好
- [ ] OfficeClaw 渠道发起对话 → Agent 加载相同偏好

### 7.6 冒烟测试

- [ ] Web Chat OAuth 登录 → 对话 → GitHub Issues 查询 → 结果正确
- [ ] 飞书 @Bot → 日历查询 → 结果正确
- [ ] API Key 方式 → `/invocations` → 工具调用正常
- [ ] Memory 跨 Session 生效
- [ ] 所有 Outbound 认证模式可用（User Federation / M2M / STS）

### 7.7 文档

- [ ] README.md 完善（项目介绍、快速开始、架构图链接）
- [ ] API 文档（FastAPI 自动生成的 Swagger UI）
- [ ] 部署文档（环境变量说明、前置条件）

## 依赖

- Epic 1-6 全部完成

## 参考

- `architecture/devops/cicd.md`
- `architecture/overall_architecture.md` #7 部署配置
- `architecture/frontend_architecture.md`
