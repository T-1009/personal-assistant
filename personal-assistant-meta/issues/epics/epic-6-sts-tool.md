---
status: backlog
---

# Epic 6: Outbound STS (云资源 Tool)

本 Phase 实现 Agent 获取华为云 STS 临时凭证，代表用户操作云资源（OBS、RDS 等）。

---

## 背景

运维场景中，用户希望通过对话管理云资源。Agent 需要获取临时 STS Token 才能访问 OBS 存储桶或 RDS 实例。本 Phase 验证 STS 模式。

## 范围

- 创建 AgentArts `huaweicloud-sts-provider` Credential Provider（STS 类型）
- `app/tools/cloud_tools.py` — 云资源工具函数
- 工具注册到 LangGraph
- 验证：Agent 获取 STS Token 并访问云资源

## 不涉及

- 完整的云资源管理功能（先做 1-2 个典型操作验证链路）
- 复杂的 IAM 权限策略

## 任务拆解

### 6.1 IAM Agency 创建

- [ ] 在华为云 IAM 控制台创建 Agency（委托）
  - 委托方：AgentArts 的 Workload Identity
  - 被委托方：云服务（OBS / RDS）
  - 权限：最小权限原则（如 OBS 只读）
- [ ] 获取 Agency URN

### 6.2 Credential Provider 创建

- [ ] 通过 AgentArts SDK 或控制台创建 `huaweicloud-sts-provider`
  - type: STS
  - agency_urn: 上面创建的 Agency URN
- [ ] 验证 Provider 创建成功

### 6.3 云资源工具函数

- [ ] `app/tools/cloud_tools.py`
  - `list_obs_objects(bucket)` — 列出 OBS 桶中对象
  - `get_obs_object(bucket, key)` — 获取 OBS 对象内容
  - （其他云资源操作按需添加）
- [ ] 工具函数设计为纯函数，sts_credentials 由调用方注入

### 6.4 Token 获取集成

- [ ] 使用 `@require_sts_token(provider_name="huaweicloud-sts-provider")` 或直接调 IdentityClient
- [ ] 返回的 StsCredentials 包含 access_key_id、secret_access_key、security_token

### 6.5 工具注册与验证

- [ ] 注册到 LangGraph ToolNode
- [ ] 更新 system prompt
- [ ] 验证：用户说 "帮我看看 my-bucket 里有哪些文件"，Agent 返回 OBS 对象列表

## 依赖

- Epic 1（Agent 骨架）完成
- Epic 3（Inbound Identity）完成

## 参考

- ADR-003: AgentArts 平台（Identity STS 部分）
- `architecture/overall_architecture.md` #4.2 Outbound 认证
