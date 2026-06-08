---
status: backlog
---

# Chore 1: 首次部署至 AgentArts Runtime 生产环境

将 Personal Assistant 服务首次部署到 AgentArts Runtime（`cn-southwest-2`），打通容器构建 → SWR 推送 → Runtime 启动 → 冒烟验证的完整链路。

---

## 背景

项目已完成核心骨架开发（Feature 1 Agent Skeleton），`.agentarts_config.yaml` 和 `Dockerfile` 均已就位，现在需要将服务实际部署到 AgentArts Runtime 上，让外部流量可以访问。

部署分层关系见 [architecture/devops/cicd.md#5-分层决策总结](../../architecture/devops/cicd.md#5-分层决策总结)：本 chore 聚焦 **Layer 1 — AgentArts 层**，通过 `agentarts launch` 完成容器部署。

## 范围

- **Docker 镜像构建**：ARM64 架构镜像（`linux/arm64`）
- **SWR 推送**：推送到 `swr.cn-southwest-2.myhuaweicloud.com/personal-assistant-org/agent_personal_assistant`
- **agentarts launch**：在 AgentArts 控制台启动 Runtime 实例
- **冒烟验证**：`/ping` 健康检查 + `/invocations` 对话调用
- **环境变量配置**：MaaS API Key、DeepSeek API Key 等密文注入
- **可观测性确认**：Tracing / Metrics / Logs 控制台可查看

## 前置条件 / 依赖

| 前置项 | 状态 | 说明 |
|--------|------|------|
| `Dockerfile` 可用 | ✅ 已有 | `personal-assistant-service/Dockerfile`，基于 `uv:python3.12-bookworm` |
| `.agentarts_config.yaml` 配置完整 | ✅ 已有 | entrypoint、SWR、network、observability 均已配置 |
| 华为云 AK/SK 认证 | ❓ 需确认 | `HUAWEICLOUD_SDK_AK` / `HUAWEICLOUD_SDK_SK` 环境变量 |
| `agentarts` CLI 安装 | ❓ 需确认 | `pip install agentarts-sdk` |
| Docker 环境（ARM64） | ❓ 需确认 | 本地 ARM64 机器或 buildx QEMU 模拟；Docker < 27 或设置 `BUILDKIT_USE_OCI_MEDIA_TYPES=0` |
| SWR 组织/仓库已创建 | ✅ auto_create | `organization_auto_create: true` + `repository_auto_create: true` |
| MaaS API Key 有效 | ❓ 需确认 | `MAAS_API_KEY` 环境变量 |
| DeepSeek API Key 有效 | ❓ 需确认 | `DEEPSEEK_API_KEY` 环境变量 |

## 任务拆解

### 1. 前置环境检查

- [ ] 确认 `agentarts` CLI 已安装（`agentarts --version`）
- [ ] 确认华为云 AK/SK 已配置（`echo $HUAWEICLOUD_SDK_AK`）
- [ ] 确认 Docker 环境可用（`docker version`），且支持 `linux/arm64`
- [ ] 确认 Docker 版本 < 27，或已设置 `export BUILDKIT_USE_OCI_MEDIA_TYPES=0`
- [ ] 确认工作目录为 `personal-assistant-service/`

### 2. 构建 Docker 镜像

- [ ] 在项目根目录执行 ARM64 镜像构建：
  ```bash
  docker build --platform linux/arm64 \
    -f personal-assistant-service/Dockerfile \
    -t swr.cn-southwest-2.myhuaweicloud.com/personal-assistant-org/agent_personal_assistant:latest \
    .
  ```
- [ ] 验证镜像构建成功（`docker images | grep agent_personal_assistant`）

### 3. 推送至 SWR

- [ ] 登录 SWR：
  ```bash
  docker login swr.cn-southwest-2.myhuaweicloud.com
  ```
  （用户名：`cn-southwest-2@<AK>`，密码：通过 `printf "$AK" | openssl dgst -binary -sha256 -hmac "$SK" | od -An -vtx1 | sed 's/[^ ]*//g' | sed 's/ //g'` 生成）
- [ ] 推送镜像：
  ```bash
  docker push swr.cn-southwest-2.myhuaweicloud.com/personal-assistant-org/agent_personal_assistant:latest
  ```

### 4. AgentArts Launch 部署

- [ ] 在 `personal-assistant-service/` 目录下执行：
  ```bash
  agentarts launch
  ```
- [ ] 确认控制台输出 Runtime 访问域名
- [ ] 在 AgentArts 控制台确认 Runtime 实例状态为「运行中」

### 5. 冒烟验证

- [ ] 健康检查：
  ```bash
  curl -s <runtime-domain>/ping
  ```
  期望返回：`{"status": "ok"}`

- [ ] 对话调用：
  ```bash
  curl -s -X POST <runtime-domain>/invocations \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer <api-key>" \
    -d '{"message": "你好，请简单介绍一下你自己"}'
  ```
  期望返回：包含 `response` 字段的 JSON

### 6. 可观测性确认

- [ ] 在 AgentArts 控制台「观测 > 全链路 Trace」查看部署后产生的 Trace
- [ ] 确认 Metrics 面板有数据（QPS、延迟等）
- [ ] 确认「日志」页面可查看容器 stdout/stderr 输出

### 7. 环境变量密文确认

- [ ] 确认以下环境变量已正确注入且不可在日志/控制台明文泄露：
  - `MAAS_API_KEY`
  - `DEEPSEEK_API_KEY`
  - `MODEL_API_KEY`

## 注意事项 / Pitfalls

1. **ARM64 强制要求**：AgentArts Runtime 仅支持 `linux/arm64`。若本地为 X86 机器，需使用 `docker buildx` + QEMU：
   ```bash
   docker buildx create --use --name arm64-builder
   docker buildx build --platform linux/arm64 --load -t <image> .
   ```

2. **OCI 格式不兼容**：Docker 27+ 默认生成 OCI 格式镜像，SWR 不支持。构建前务必设置：
   ```bash
   export BUILDKIT_USE_OCI_MEDIA_TYPES=0
   ```

3. **IAM 权限**：若使用 IAM 子账号，需确保有 SWR FullAccess 权限。

4. **Python 版本**：AgentArts Runtime 要求 Python ≥ 3.10（当前使用 3.12 ✅）。

5. **Region 锁定**：仅支持 `cn-southwest-2`（西南贵阳一）。

## 参考

| 文档 | 路径 |
|------|------|
| AgentArts 平台架构 | `architecture/cloud-service/agentarts.md` |
| 总体架构 | `architecture/overall_architecture.md` |
| CI/CD 部署策略 | `architecture/devops/cicd.md` |
| 部署配置 | `personal-assistant-service/.agentarts_config.yaml` |
| Dockerfile | `personal-assistant-service/Dockerfile` |
| Feature 9 部署规划 | `issues/features/feature-9-deployment/issue.md` |
