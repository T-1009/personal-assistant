---
status: backlog
---

# Epic 4: Outbound User Federation (GitHub Tool)

本 Phase 实现 Agent 以用户身份调用 GitHub API（User Federation 模式）。用户完成一次 OAuth 授权后，Agent 可以代表用户查询 Issues、PR、仓库信息。

---

## 背景

Personal Assistant 的核心价值之一是 "以用户身份访问外部服务"。本 Phase 验证最典型的 User Federation 场景：Agent 帮你查 GitHub Issues。底层走 AgentArts Identity 的 OAuth2 Credential Provider。

## 范围

- 创建 GitHub OAuth App + AgentArts `github-provider` Credential Provider
- `app/tools/github_tools.py` — GitHub 工具函数
- 工具注册到 LangGraph 的 ToolNode
- 验证：用户说 "帮我查我的 GitHub Issues"，Agent 调 GitHub API 并返回结果

## 不涉及

- Google Calendar / Gmail 工具（结构相同，后续可复用模式快速添加）
- M2M 模式（Phase 5）
- STS 模式（Phase 6）

## 任务拆解

### 4.1 GitHub OAuth App 创建

- [ ] 在 GitHub Settings → Developer settings 创建 OAuth App
- [ ] 配置 Callback URL（支持 AgentArts Identity 的回调地址）
- [ ] 获取 client_id 和 client_secret

### 4.2 Credential Provider 创建

- [ ] 通过 AgentArts SDK 或控制台创建 `github-provider`
  - type: OAuth2
  - vendor: github
  - client_id / client_secret
- [ ] 验证 Provider 创建成功

### 4.3 GitHub 工具函数

- [ ] `app/tools/github_tools.py`
  - `list_issues(owner, repo, state="open")` — 查询 Issues 列表
  - `get_issue(owner, repo, issue_number)` — 查询单个 Issue
  - `list_repos()` — 查询用户仓库
- [ ] 工具函数设计为**纯函数**，access_token 由调用方注入
  - 函数签名：`async def list_issues(owner, repo, access_token: str)`
  - 不直接依赖 `@require_access_token` 装饰器（便于本地测试）

### 4.4 Token 获取集成

- [ ] `app/tools/github_tools.py` 或独立模块
  - `get_github_token(user_token)` — 调 AgentArts Identity SDK 获取 access_token
  - 使用 `require_access_token(provider_name="github-provider", ...)` 
  - 或直接调 IdentityClient API
- [ ] 在 ToolNode 执行前注入 token

### 4.5 LangGraph 工具注册

- [ ] 将 GitHub 工具函数注册到 LangGraph ToolNode
  - 使用 `@tool` 装饰器或 `StructuredTool.from_function()`
  - 定义参数 schema（owner、repo、issue_number 等）
- [ ] 更新 system prompt，告知 LLM 何时使用 GitHub 工具

### 4.6 首次授权流程

- [ ] 用户首次调 GitHub 工具时，AgentArts Identity 返回授权 URL
- [ ] Agent 将授权 URL 展示给用户
- [ ] 用户在浏览器完成授权
- [ ] 后续调用自动使用 refresh token

### 4.7 验证

- [ ] 用户说 "帮我查一下 my-org/my-repo 的 open issues"
- [ ] Agent 调 GitHub API，返回 Issue 列表
- [ ] 跨 Session：下次对话无需重新授权

## 依赖

- Epic 1（Agent 骨架）完成
- Epic 3（Inbound Identity）完成（需要用户身份上下文）

## 参考

- ADR-003: AgentArts 平台（Identity 部分）
- `architecture/overall_architecture.md` #4 Identity 设计
