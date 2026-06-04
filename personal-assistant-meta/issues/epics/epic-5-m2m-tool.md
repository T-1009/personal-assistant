---
status: backlog
---

# Epic 5: Outbound M2M (内部 API Tool)

本 Phase 实现 Agent 以自身服务身份调用企业内部 API（M2M 模式）。Agent 使用预配置的 API Key 访问内部系统（CRM、OA 等）。

---

## 背景

企业内部系统通常不允许 User Federation（员工个人 OAuth），而是通过 API Key 做服务间调用。本 Phase 验证 M2M 模式：Agent 以 Personal Assistant 服务身份调用内部 API，获取信息后回复用户。

## 范围

- 创建 AgentArts `internal-api-provider` Credential Provider（API Key 类型）
- `app/tools/internal_tools.py` — 内部 API 工具函数
- 工具注册到 LangGraph
- 验证：Agent 调内部 API 并返回结果

## 不涉及

- 真实内部 API 对接（本 Phase 可以用 Mock API 验证 M2M 链路）
- STS 模式（Phase 6）

## 任务拆解

### 5.1 Credential Provider 创建

- [ ] 通过 AgentArts SDK 或控制台创建 `internal-api-provider`
  - type: API Key
  - api_key: 内部系统的 API Key
- [ ] 验证 Provider 创建成功

### 5.2 内部 API 工具函数

- [ ] `app/tools/internal_tools.py`
  - `search_internal_knowledge(query)` — 搜索内部知识库
  - `query_employee_info(name)` — 查询员工信息
  - （具体工具取决于内部 API，先用 1-2 个典型场景验证链路）
- [ ] 工具函数设计为纯函数，api_key 由调用方注入

### 5.3 Token 获取集成

- [ ] 使用 `@require_api_key(provider_name="internal-api-provider")` 或直接调 IdentityClient
- [ ] 在工具执行前注入 api_key

### 5.4 工具注册与 System Prompt

- [ ] 注册到 LangGraph ToolNode
- [ ] 更新 system prompt，添加内部工具使用说明

### 5.5 验证

- [ ] 用户说 "帮我查一下张三的工位"，Agent 调内部 API 返回结果
- [ ] 确认 API Key 不会泄露到 Agent 回复中

## 依赖

- Epic 1（Agent 骨架）完成
- Epic 3（Inbound Identity）完成

## 参考

- ADR-003: AgentArts 平台（Identity M2M 部分）
- `architecture/overall_architecture.md` #4.2 Outbound 认证
