# Feature 17：GitHub MCP Activity Data Source Implementation Plan

> 状态：Draft  
> 日期：2026-07-10  
> 范围：通过 AgentArts MCP Gateway 接入 GitHub 官方 remote MCP，新增 Service 内部 GitHub activity data source；不新增 Report root capability。

## 1. 概要

本 Feature 先实现 **GitHub MCP activity data source**，为后续 Report root capability 提供工程活动输入。它的目标是验证并固化 AgentArts MCP Gateway 的接入方式、凭据链路、Target read-only 配置、GitHub MCP 原子工具映射和统一事件模型。

本 Feature 不面向用户新增报表能力，不注册 `generate_report`，也不把 GitHub MCP 的全部原子工具直接交给 Agent。Service 只暴露内部 source wrapper，由后续 Feature 18 消费。

设计目标：

- 使用 AgentArts MCP Gateway 连接 GitHub 官方 remote MCP。
- GitHub Target 使用 read-only endpoint 和最小 PAT 权限。
- Service 通过 WAT → STS provider → 临时 IAM 凭据调用 Gateway，不在 Runtime 配置长期 AK/SK。
- 在 Service 内封装 `github_mcp_tools.py`，输出 `GitHubActivityEvent`。
- 对 401 / 403 / 429 / Gateway unavailable 等错误做 typed warning 映射。

## 2. 架构边界

图类型：**Component Diagram（组件图）**。用于说明本 Feature 的组件边界。

```mermaid
flowchart TB
    Service["personal-assistant-service"]
    Source["tools/github_mcp_tools.py<br/>GitHub activity source"]
    MCPConfig["app/mcp<br/>Gateway config + IAM signing"]
    Adapter["LangChain / LangGraph MCP adapter"]
    Gateway["AgentArts MCP Gateway<br/>入站 IAM"]
    Target["GitHub MCP Target<br/>read-only<br/>Authorization: Bearer PAT"]
    GitHubMCP["GitHub remote MCP<br/>/mcp/readonly"]
    GitHubAPI["GitHub API"]

    Service --> Source
    Source --> MCPConfig
    MCPConfig --> Adapter
    Adapter --> Gateway
    Gateway --> Target
    Target --> GitHubMCP
    GitHubMCP --> GitHubAPI
```

### 2.1 不做 Report

本 Feature 的输出是 GitHub 工程活动数据源，不是用户可见的报表能力。

```text
本 Feature 新增:
  github_mcp_resolve_identity(...)
  github_mcp_list_repositories(...)
  github_mcp_search_activity(...)
  github_mcp_get_detail(...)

后续 Feature 18 才新增:
  generate_report(...)
```

### 2.2 不替代现有 GitHub local tools

当前 GitHub local tools 继续负责 repository browsing、目录、文件读取、代码搜索和 star。GitHub MCP data source 只补齐 activity timeline。

| 能力 | 本 Feature 处理方式 |
|---|---|
| commits / PR / issue / review / comment activity | 新增 GitHub MCP activity source |
| 仓库目录 / 文件读取 / 代码搜索 / star | 继续使用现有 GitHub local tools |
| GitHub 写操作 | 不实现 |
| user-delegated GitHub activity | 不实现，后续单独设计 |

## 3. AgentArts MCP Gateway 配置

`gateway-github-mcp` 与 `target-github-mcp` 在华为云 AgentArts 控制台手动创建和维护。本 Feature 不通过代码创建 / 更新 Gateway 或 Target。

### 3.1 Gateway 入站

| 配置项 | 值 |
|---|---|
| Gateway name | `gateway-github-mcp` |
| 协议类型 | MCP |
| 入站认证 | IAM |
| 网络模式 | 按当前 AgentArts Runtime / Gateway 可达性配置 |

### 3.2 GitHub Target 出站

| 配置项 | 值 |
|---|---|
| Target name | `target-github-mcp` |
| Target URL | `https://api.githubcopilot.com/mcp/readonly` |
| Transport | Streamable HTTP |
| 出站认证类型 | API Key |
| 注入位置 | Header / 请求头 |
| Header name / 参数名称 | `Authorization` |
| Prefix / 前缀 | `Bearer` |
| Secret value / API Key 值 | `<GitHub PAT>` |
| 实际出站 header | `Authorization: Bearer <GitHub PAT>` |

若 AgentArts Target 支持自定义 header，额外配置：

| Header | 值 | 用途 |
|---|---|---|
| `X-MCP-Readonly` | `true` | 明确只读模式 |
| `X-MCP-Toolsets` | `repos,issues,pull_requests` | 限制到工程活动所需 toolsets |

GitHub PAT 优先使用 fine-grained PAT，并限制到本项目需要读取的 repository；权限只授予 Metadata read、Contents read、Issues read、Pull requests read 等只读权限。若只能使用 classic PAT，必须在 staging 配置中明确权限范围和 demo 边界。

## 4. Gateway 入站 IAM 签名凭据路径

图类型：**Data Flow / Trust Boundary Diagram（数据流 / 信任边界图）**。用于说明 Service 调 Gateway 的凭据流。

```mermaid
flowchart LR
    Request["Web Chat request"] --> Runtime["AgentArts Runtime"]
    Runtime -->|"inject header"| WAT["X-HW-AgentGateway-Workload-Access-Token"]
    WAT --> Context["AgentArtsRuntimeContext"]
    Context --> Identity["AgentArts Identity<br/>STS provider"]
    Identity --> STS["Temporary IAM credentials"]
    STS --> Signer["HuaweiCloud API signing SDK"]
    Signer --> Gateway["AgentArts MCP Gateway"]
```

Production Runtime：

- Web Chat 请求进入 Service 时，AgentArts Gateway 已向 Runtime 容器注入 `X-HW-AgentGateway-Workload-Access-Token`。
- `main.py` 按现有架构将该 header 写入 `AgentArtsRuntimeContext`。
- GitHub MCP source 通过 AgentArts Identity STS provider 获取临时 IAM 凭据。
- Service 使用华为云 API signing SDK 对调用 `GITHUB_MCP_GATEWAY_URL` 的 HTTP 请求签名。

本地开发：

- 没有 `X-HW-AgentGateway-Workload-Access-Token` header 时，沿用现有 SDK fallback。
- SDK 从 `.agent_identity.json` / customer-owned local workload 获取 WAT，再向 AgentArts Identity 换取 STS 临时凭据。
- 真实连云调试前，先按 `personal-assistant-meta/architecture/cloud-service/huaweicloud/agent-identity.md` 创建或验证 `pa-local-jwt-workload`。

禁止事项：

- 不把长期 AK/SK 放进 `.agentarts_config.yaml`、`.env`、tool schema、日志或 LLM-visible error。
- 若手动 smoke test 需要 `HUAWEICLOUD_SDK_AK` / `HUAWEICLOUD_SDK_SK`，仅限本地 CLI / helper script 使用，不作为 Service 默认运行路径。

## 5. Service 侧变更

### 5.1 新增配置

新增 typed settings：

| Setting | 说明 |
|---|---|
| `GITHUB_MCP_ENABLED` | 是否启用 GitHub MCP data source |
| `GITHUB_MCP_GATEWAY_URL` | 已创建 Gateway 的 MCP endpoint |
| `GITHUB_MCP_AUTH_MODE` | 首期固定为 `iam` |
| `GITHUB_MCP_STS_PROVIDER_NAME` | 用于获取临时 IAM 凭据的 AgentArts Identity STS provider |
| `GITHUB_MCP_TIMEOUT_SECONDS` | Gateway / MCP 调用 timeout |
| `GITHUB_MCP_TOOL_PREFIX` | 远程 MCP tool name prefix，便于诊断冲突 |

### 5.2 新增 `app/mcp/`

`app/mcp/` 只做薄封装：

- 读取 GitHub MCP settings；
- 构造 MCP adapter client；
- 注入 IAM signed headers；
- 执行 `tools/list` capability check；
- 统一 timeout / retry / error mapping；
- 过滤 credential，不让 token、PAT、AK/SK、签名 header 进入日志和 tool result。

Service 连接 AgentArts MCP Gateway 时优先评估 `langchain-mcp-adapters`。项目内不自实现 MCP 协议。

### 5.3 新增 `app/tools/github_mcp_tools.py`

内部 source functions：

| Function | 职责 |
|---|---|
| `github_mcp_resolve_identity` | 调 `get_me`，解析 platform GitHub account |
| `github_mcp_list_repositories` | 搜索 / 枚举平台账号可见仓库，隐藏归档或不可访问仓库 |
| `github_mcp_search_activity` | 按时间窗口、repository、actor、event type 聚合 commits / PR / issues / reviews / comments |
| `github_mcp_get_detail` | 对 commit / PR / issue 拉取详情、评论、review、文件变更和统计信息 |

这些 functions 可以作为 Service 内部 callable 实现，也可以在 LangGraph 内作为非 root tool 使用；首期不把它们作为用户可主动选择的 root capability。

## 6. 数据模型

`GitHubActivityEvent`：

| 字段 | 说明 |
|---|---|
| `provider` | 固定为 `github`，保留字段用于后续扩展其他代码平台 |
| `event_type` | `commit`、`pull_request`、`issue`、`review`、`comment` |
| `repository` | 仓库 full name |
| `external_id` | 第三方平台 ID / number / sha |
| `title` | 活动标题 |
| `url` | 原始平台链接 |
| `actor` | 活动发起人 |
| `state` | open / closed / merged 等 |
| `created_at` / `updated_at` | 时间戳 |
| `summary` | 面向后续报表的短摘要 |
| `metrics` | additions、deletions、changed_files、comment_count 等可选指标 |

`github_mcp_search_activity` 输入示例：

```json
{
  "start_at": "2026-07-01T00:00:00+08:00",
  "end_at": "2026-07-08T23:59:59+08:00",
  "timezone": "Asia/Shanghai",
  "provider": "github",
  "repositories": ["git-malu/personal-assistant"],
  "actor": "platform",
  "event_types": ["commit", "pull_request", "issue", "review", "comment"],
  "limit": 100,
  "cursor": null
}
```

## 7. 官方 MCP 原子工具映射

官方 GitHub MCP Server 暴露 GitHub API 级别的原子工具；Service 通过 source wrapper 做聚合和归一化。

| GitHub activity source function | 调用的官方 GitHub MCP 原子工具 | 聚合职责 |
|---|---|---|
| `github_mcp_resolve_identity` | `get_me` | 获取 GitHub MCP Target 平台授权身份，用于 `actor = platform` 和活动归因 |
| `github_mcp_list_repositories` | `search_repositories`，以及 runtime `tools/list` 中可用的 repository listing 工具 | 根据关键词、更新时间和权限范围筛选候选仓库 |
| `github_mcp_search_activity` | commits: `list_commits` / `get_commit`；pull requests: `list_pull_requests` / `search_pull_requests` / `pull_request_read`；issues: `list_issues` / `search_issues` / `issue_read`；actions 可选：`actions_list` / `actions_get` | 按时间窗口、仓库、actor、event type 聚合活动 |
| `github_mcp_get_detail` | `get_commit`、`pull_request_read`、`issue_read`，以及 runtime 中可用的 comments / reviews / files 相关只读工具 | 对单条活动拉取详情 |

`github_mcp_search_activity` 聚合流程：

1. 将 `start_at` / `end_at` 按 `timezone` 归一化为 UTC 时间窗口。
2. 调用 `github_mcp_resolve_identity` 解析 GitHub MCP Target 平台授权身份；当 `actor = "platform"` 时，用该 login 过滤 commits、PR、issues、reviews 和 comments。
3. 如果没有指定 `repositories`，先调用 `github_mcp_list_repositories` 获取候选仓库。
4. 按 `event_types` 分批调用官方 MCP 原子工具；每类数据独立分页。
5. 对列表结果先做轻量过滤；只有需要展开时，才调用 detail tools。
6. 将不同原始对象映射为统一 `GitHubActivityEvent`。

## 8. 测试计划

### 8.1 单元测试

- MCP source schema 不包含 `access_token`、`api_key`、`secret`、PAT、AK/SK 或 STS 字段。
- `github_mcp_search_activity` 正确处理：
  - 时间窗口；
  - provider 固定为 `github`；
  - repository filter；
  - actor = `platform`；
  - event type filter；
  - limit / cursor。
- GitHub mock 覆盖 commits、pull requests、issues、reviews、comments、分页、401、403、429。

### 8.2 集成测试

- `GITHUB_MCP_ENABLED=true` 时，Service 可以初始化 GitHub MCP source。
- GitHub MCP source 启动检查确认 Gateway Target 使用 read-only endpoint 或 `X-MCP-Readonly: true`。
- 不提供通用 raw MCP tool passthrough。
- Gateway unavailable 降级为 unavailable warning。
- `GITHUB_MCP_AUTH_MODE=iam` 时，缺少 `GITHUB_MCP_STS_PROVIDER_NAME`、STS 兑换失败或 IAM 签名返回 401 / 403，均映射为 typed warning。

### 8.3 E2E / Staging 验证

- Production Runtime 请求路径能从 `X-HW-AgentGateway-Workload-Access-Token` 进入 `AgentArtsRuntimeContext`，并通过 `GITHUB_MCP_STS_PROVIDER_NAME` 换取临时 IAM 凭据完成 Gateway 调用。
- Gateway Target 指向 `https://api.githubcopilot.com/mcp/readonly`，或等效配置 `X-MCP-Readonly: true`。
- Gateway Target 注入 `Authorization: Bearer <GitHub PAT>`，PAT 使用只读最小权限。
- `github_mcp_search_activity` 能返回 staging repository 的 commits / PR / issues。
- token、PAT、AK/SK、STS、签名 header 不进入 SSE、日志、tool result 或 LLM-visible error。

## 9. 预期项目文件目录

```text
personal-assistant/
├── personal-assistant-meta/
│   ├── issues/features/backlog/feature-17-github-mcp-data-source/
│   │   ├── issue.md
│   │   └── plan.md
│   ├── specs/
│   │   ├── overall_specifications.md   # 修改：登记 GitHub MCP activity data source
│   │   └── dictionary.md               # 修改：补充 GitHubActivityEvent / GitHub MCP 术语
│   └── architecture/
│       ├── overall_architecture.md      # 修改：登记 AgentArts MCP Gateway data source
│       └── backend_architecture.md      # 修改：补充 app/mcp 与 GitHub MCP source
└── personal-assistant-service/
    ├── app/
    │   ├── mcp/
    │   │   ├── __init__.py
    │   │   ├── gateway_client.py
    │   │   └── github_activity.py
    │   ├── tools/
    │   │   └── github_mcp_tools.py
    │   └── config.py
    └── tests/
        ├── test_github_mcp_tools.py
        └── test_mcp_gateway_auth.py
```

## 10. 完成后交付给 Feature 18 的契约

Feature 18 只依赖以下稳定契约：

- `github_mcp_search_activity(...) -> list[GitHubActivityEvent]`；
- `github_mcp_get_detail(...) -> GitHubActivityEvent detail`；
- source unavailable / partial failure 以 typed warning 表达；
- GitHub MCP source 不泄露 credential；
- `actor = platform` 表示 PAT / platform GitHub account。
