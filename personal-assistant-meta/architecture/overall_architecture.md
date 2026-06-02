# Personal Assistant — 总体架构设计

> 版本：v0.2 | 状态：Draft | 基于 AgentArts 平台

---

## 1. 架构总览

### 1.1 整体架构

```mermaid
flowchart TB
    subgraph Clients["客户端"]
        WebChat["Web Chat UI<br/>(React/Vue)"]
        CliChat["CLI Chat"]
        MobileChat["Mobile App"]
    end

    subgraph IdPs["Identity Provider（外部）"]
        GoogleIdP["Google OAuth"]
        GitHubIdP["GitHub OAuth"]
        CustomIdP["自定义 IdP<br/>(OIDC compatible)"]
    end

    subgraph AgentArts["AgentArts 平台"]
        direction TB

        subgraph Inbound["Inbound — 入站认证"]
            IAM["IAM Auth<br/>(AK/SK Signature)"]
            JWT["Custom JWT Auth<br/>(OIDC Discovery)"]
            KeyAuth["API Key Auth"]
        end

        Runtime["Agent Runtime<br/>Personal Assistant<br/>(LangGraph + Python)"]

        subgraph IdentitySvc["Identity Service"]
            WorkloadId["Workload Identity<br/>(Agent 工作负载身份)"]
            CredProviders["Credential Providers<br/>API Key / OAuth2 / STS"]
        end

        MemorySvc["Memory Service<br/>Short-term + Long-term<br/>Semantic / Preference / Episodic"]
        Gateway["MCP Gateway<br/>API → MCP Tool 转换"]

        subgraph Observability["观测"]
            Tracing["全链路 Trace"]
            Logs["运行日志"]
            Eval["自动评估"]
        end
    end

    subgraph External["外部服务"]
        GoogleAPI["Google APIs<br/>(Calendar, Gmail...)"]
        GitHubAPI["GitHub API<br/>(Issues, PRs...)"]
        InternalAPI["企业内部 API<br/>(CRM, OA...)"]
        HwCloudRes["云资源<br/>(OBS, RDS...)"]
    end

    Clients -->|"HTTPS + Auth Header"| Inbound
    Inbound -->|"验证通过 → RequestContext"| Runtime
    Runtime -->|"Memory SDK"| MemorySvc
    Runtime -->|"Gateway SDK"| Gateway
    Runtime -->|"Identity SDK<br/>Outbound OAuth/API Key/STS"| IdentitySvc
    Runtime -->|"OTEL"| Observability

    IdentitySvc -->|"get_resource_oauth2_token()<br/>USER_FEDERATION"| GoogleIdP
    IdentitySvc -->|"get_resource_oauth2_token()<br/>USER_FEDERATION"| GitHubIdP
    IdentitySvc -->|"get_resource_api_key()"| InternalAPI
    IdentitySvc -->|"get_resource_sts_token()"| HwCloudRes
    GoogleIdP --> GoogleAPI
    GitHubIdP --> GitHubAPI
```

### 1.2 技术选型

| 层级 | 选型 | 说明 |
|------|------|------|
| **Agent 编排** | LangGraph (Python) | 有状态图编排，支持条件路由和工具调用循环 |
| **LLM** | DeepSeek-V3.2 (via MaaS) | OpenAI-compatible API，部署在华为云 |
| **Runtime** | AgentArts Runtime | 容器化部署，ARM64 架构，cn-southwest-2 区域 |
| **Memory** | AgentArts Memory SDK | 短期+长期记忆，语义/偏好/情景三种策略 |
| **Identity** | AgentArts Identity SDK | Inbound JWT/API Key + Outbound OAuth2/M2M/STS |
| **Gateway** | AgentArts MCP Gateway | API 定义 → MCP Tool 自动转换 |
| **可观测** | OTEL (AgentArts 内置) | Tracing + Logging + Metrics |
| **Container** | Docker (linux/arm64) | Python 3.10+ |

---

## 2. 认证流详解

```mermaid
sequenceDiagram
    actor User as 用户
    participant Client as Chat UI
    participant RT as AgentArts Runtime
    participant ID as Identity Service
    participant Agent as Personal Assistant
    participant Ext as External API (GitHub)

    Note over User,Ext: === Inbound 认证（用户 → Agent） ===

    User->>Client: 打开聊天界面
    Client->>RT: POST /invocations<br/>Authorization: Bearer {OAuth2_Access_Token}
    RT->>ID: 验证 JWT/API Key
    ID-->>RT: 验证通过，注入 RequestContext<br/>(包含 user_id, scopes 等)
    RT->>Agent: handler(payload, context)

    Note over User,Ext: === Outbound 认证（Agent → 外部服务） ===

    User->>Agent: "帮我查 GitHub Issues"

    Agent->>ID: get_resource_oauth2_token(<br/>  provider_name="github",<br/>  scopes=["repo", "read:user"],<br/>  agent_identity_token=context.user_token<br/>)
    ID-->>Agent: GitHub Access Token

    Agent->>Ext: GET /repos/{owner}/{repo}/issues<br/>Authorization: Bearer {GitHub_Token}
    Ext-->>Agent: Issues List

    Agent-->>Client: "你当前有 3 个 open issue: ..."
    Client-->>User: 展示结果
```

---

## 3. Identity 设计

### 3.1 Inbound — 用户认证到 Agent

AgentArts Runtime 通过 `agentarts_config.yaml` 中 `runtime.identity_configuration` 配置三种 Inbound 认证方式：

```yaml
runtime:
  identity_configuration:
    authorizer_type: CUSTOM_JWT          # IAM | CUSTOM_JWT | KEY_AUTH
    authorizer_configuration:
      custom_jwt:
        discovery_url: https://accounts.google.com/.well-known/openid-configuration
        allowed_audience:
          - "personal-assistant-client-id"
        allowed_clients:
          - "personal-assistant-client-id"
        allowed_scopes:
          - "openid"
          - "profile"
          - "email"
      key_auth:
        api_keys:
          - "opencode-2026-api-key-xxxxx"       # 开发调试用
```

| 认证方式 | 适用场景 | 配置 |
|----------|----------|------|
| **IAM** | 华为云内部用户（Console / CLI） | `authorizer_type: IAM` |
| **Custom JWT** | 自有 IdP 用户登录（Google / Okta / Auth0） | `authorizer_type: CUSTOM_JWT` + `discovery_url` |
| **API Key** | 开发调试 / 机器对机器调用 | `authorizer_type: KEY_AUTH` + `api_keys[]` |

> 推荐生产环境使用 **Custom JWT** 方式，通过 Google OAuth 或自有 OIDC IdP 提供用户认证。

### 3.2 Outbound — Agent 代表用户调用外部服务

AgentArts Identity SDK 提供三种 Outbound 认证模式：

| 模式 | Auth Flow | 用途 | 典型场景 |
|------|-----------|------|----------|
| **User Federation** | `USER_FEDERATION` | Agent 以用户身份调用外部 API | 查 GitHub Issues、发 Gmail、读 Google Calendar |
| **M2M** | `M2M` | Agent 以自身服务身份调用 API | 调用企业内部 CRM、OA 系统 |
| **STS Token** | — | Agent 获取云资源访问凭证 | 操作 OBS 对象存储、访问 RDS |

#### 3.2.1 Credential Provider 创建

通过 AgentArts SDK 创建各类 Credential Provider：

```python
from agentarts.sdk.services.identity import IdentityClient

client = IdentityClient(region="cn-southwest-2")

# 1. 创建 Workload Identity（Agent 的工作负载身份）
workload = client.create_workload_identity(
    name="personal-assistant-workload",
    description="Personal Assistant Agent 工作负载身份"
)

# 2. OAuth2 Provider — GitHub（User Federation）
github_provider = client.create_oauth2_credential_provider(
    name="github-provider",
    vendor="github",
    client_id="your-github-oauth-app-client-id",
    client_secret="your-github-oauth-app-client-secret"
)

# 3. OAuth2 Provider — Google（User Federation）
google_provider = client.create_oauth2_credential_provider(
    name="google-provider",
    vendor="google",
    client_id="your-google-oauth-client-id",
    client_secret="your-google-oauth-client-secret"
)

# 4. API Key Provider — 企业内部 API（M2M）
api_key_provider = client.create_api_key_credential_provider(
    name="internal-api-provider",
    api_key="sk-internal-api-xxxxx"
)

# 5. STS Provider — 云资源（M2M）
sts_provider = client.create_sts_credential_provider(
    name="huaweicloud-sts-provider",
    agency_urn="urn:agency:your-agency",
    tags=[{"key": "env", "value": "prod"}]
)
```

#### 3.2.2 凭据装饰器使用

```python
from agentarts.sdk import require_access_token, require_api_key, require_sts_token
from agentarts.sdk.identity.types import StsCredentials
from typing import Optional
import httpx

# === User Federation: 以用户身份调用 GitHub ===
@require_access_token(
    provider_name="github-provider",
    scopes=["repo", "read:user"],
    auth_flow="USER_FEDERATION"
)
async def get_github_issues(owner: str, repo: str, access_token: Optional[str] = None):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        return resp.json()

# === User Federation: 以用户身份调用 Google Calendar ===
@require_access_token(
    provider_name="google-provider",
    scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    auth_flow="USER_FEDERATION"
)
async def get_google_calendar_events(access_token: Optional[str] = None):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        return resp.json()

# === M2M: Agent 以自身身份调用企业内部 API ===
@require_api_key(provider_name="internal-api-provider")
def call_internal_crm(query: str, api_key: Optional[str] = None):
    import requests
    resp = requests.get(
        f"https://crm.internal.example.com/api/search?q={query}",
        headers={"X-API-Key": api_key}
    )
    return resp.json()

# === STS: Agent 获取云资源 Token ===
@require_sts_token(
    provider_name="huaweicloud-sts-provider",
    agency_session_name="personal-assistant-session"
)
async def access_obs_file(bucket: str, key: str, sts_credentials: Optional[StsCredentials] = None):
    from obs import ObsClient
    obs_client = ObsClient(
        access_key_id=sts_credentials.access_key_id,
        secret_access_key=sts_credentials.secret_access_key,
        security_token=sts_credentials.security_token,
        server="https://obs.cn-southwest-2.myhuaweicloud.com"
    )
    return obs_client.getObject(bucket, key)
```

---

## 4. Chat Agent 设计

### 4.1 LangGraph 编排

Agent 使用 LangGraph StateGraph 实现有状态的对话编排：

```mermaid
stateDiagram-v2
    [*] --> agent: entry_point
    agent --> tools: has tool_calls
    agent --> finalize: no tool_calls
    tools --> agent: tool results
    finalize --> [*]
```

核心节点：

- **agent** — LLM 推理节点：决定是调用工具还是直接回答，注入 Memory 上下文
- **tools** — ToolNode：执行工具调用，返回结果
- **finalize** — 终止节点：保存 Memory，构建最终响应

### 4.2 Agent 代码骨架

```python
# app/personal_assistant/agent.py

import os
from typing import Dict, Any, TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agentarts.sdk import AgentArtsRuntimeApp, RequestContext

# Identity Outbound 工具
from .tools.github_tools import list_github_issues
from .tools.google_tools import get_calendar_events
from .tools.internal_tools import search_crm
from .tools.cloud_tools import read_obs_file

# Memory
from .memory import PersonalAssistantMemory

app = AgentArtsRuntimeApp()


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    response: str
    context: Optional[Dict[str, Any]]


class PersonalAssistant:
    def __init__(self):
        self.model_name = os.environ.get("MODEL_NAME", "deepseek-v3.2")
        self.memory = PersonalAssistantMemory()
        self._graph = None

        # 定义可用工具
        self.tools = [
            list_github_issues,
            get_calendar_events,
            search_crm,
            read_obs_file,
        ]

    def _build_graph(self):
        llm = ChatOpenAI(
            model=self.model_name,
            api_key=os.environ.get("MODEL_API_KEY"),
            base_url=os.environ.get("MODEL_URL",
                "https://api.modelarts-maas.com/openai/v1")
        )
        llm_with_tools = llm.bind_tools(self.tools)

        tool_node = ToolNode(self.tools)

        async def agent_node(state: AgentState) -> Dict[str, Any]:
            """核心 Agent 节点：决定调用工具还是直接回答"""
            # 注入 Memory 上下文
            memory_context = await self.memory.get_context(state)
            system_prompt = f"你是 Personal Assistant。\n{memory_context}"
            messages = [HumanMessage(content=system_prompt)] + state.get("messages", [])
            response = await llm_with_tools.ainvoke(messages)
            return {"messages": [response]}

        async def finalize_node(state: AgentState) -> Dict[str, Any]:
            """最终节点：保存 Memory，返回结果"""
            if state.get("messages"):
                last_msg = state["messages"][-1]
                await self.memory.save_interaction(state, last_msg)
            return {
                "response": state["messages"][-1].content if state.get("messages") else ""
            }

        workflow = StateGraph(AgentState)
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        workflow.add_node("finalize", finalize_node)

        workflow.set_entry_point("agent")

        # 条件路由：如需工具调用则去 tools，否则结束
        workflow.add_conditional_edges(
            "agent",
            lambda state: "tools" if state["messages"][-1].tool_calls else "finalize",
            {"tools": "tools", "finalize": "finalize"}
        )
        workflow.add_edge("tools", "agent")     # 工具结果返回 agent 继续推理
        workflow.add_edge("finalize", END)

        return workflow.compile()

    async def run(self, query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        graph = self._graph or self._build_graph()
        self._graph = graph
        result = await graph.ainvoke({
            "messages": [HumanMessage(content=query)],
            "query": query,
            "response": "",
            "context": context or {}
        })
        return {"response": result.get("response", "")}


_assistant = PersonalAssistant()


@app.entrypoint
async def handler(
    payload: Dict[str, Any],
    context: RequestContext = None   # AgentArts 自动注入
) -> Dict[str, Any]:
    """
    AgentArts Runtime entrypoint.
    RequestContext 由平台根据 Inbound Auth 结果自动注入，包含：
      - context.user_id     : 用户身份
      - context.user_token  : 用户 Token（用于 Outbound User Federation）
      - context.session_id  : 会话 ID
    """
    query = payload.get("message", "")
    user_context = {
        "user_id": context.user_id if context else None,
        "user_token": context.user_token if context else None,
        "session_id": context.session_id if context else None,
    }
    return await _assistant.run(query, user_context)


if __name__ == "__main__":
    app.run()
```

### 4.3 Agent State 数据流

```mermaid
flowchart LR
    Entry["entrypoint<br/>handler(payload, context)"] --> State["AgentState<br/>messages / query / response / context"]
    State --> AgentNode["agent_node<br/>注入 Memory → LLM 推理"]
    AgentNode -->|"tool_calls"| ToolNode["tool_node<br/>执行工具调用"]
    AgentNode -->|"无 tool_calls"| Finalize["finalize_node<br/>保存 Memory → 返回"]
    ToolNode -->|"tool results"| AgentNode
    Finalize --> Response["Dict[str, Any]<br/>{response: '...'}"]
```

---

## 5. Memory 集成

### 5.1 Memory 模型

AgentArts Memory 采用分层存储模型：

```
Space（记忆空间）
 └── Session（会话）
      ├── Messages（消息记录）
      └── Memories（抽取的记忆）
           ├── Semantic（语义记忆 — 知识/事实）
           ├── Preference（偏好记忆 — 用户习惯）
           └── Episodic（情景记忆 — 历史对话摘要）
```

- **Space**：租户级隔离单元，一个 Personal Assistant 实例对应一个 Space
- **Session**：每次对话会话，关联特定用户
- **Memory**：从 Session 消息中自动抽取的长短期记忆

### 5.2 SDK 集成代码

```python
# app/personal_assistant/memory.py

import os
from agentarts.sdk.memory import MemoryClient
from agentarts.sdk.memory.session import MemorySession
from agentarts.sdk.memory.inner.config import TextMessage, MemorySearchFilter


class PersonalAssistantMemory:
    def __init__(self):
        self.space_id = os.environ.get("MEMORY_SPACE_ID")
        self.actor_prefix = "pa-user-"
        self.assistant_id = "personal-assistant"

    async def get_context(self, state: dict) -> str:
        """获取当前 Session 的 Memory 上下文"""
        user_id = state.get("context", {}).get("user_id", "anonymous")
        if not self.space_id:
            return ""

        session = MemorySession(
            space_id=self.space_id,
            actor_id=f"{self.actor_prefix}{user_id}",
            assistant_id=self.assistant_id
        )

        # 搜索长期记忆中的用户偏好
        results = session.search_long_term_memories(
            filters=MemorySearchFilter(query="user preferences", top_k=5)
        )

        context_parts = []
        for r in results.results:
            record = r.get("record", {})
            context_parts.append(record.get("content", ""))

        return "\n".join(context_parts) if context_parts else ""

    async def save_interaction(self, state: dict, last_message) -> None:
        """保存对话到 Memory"""
        user_id = state.get("context", {}).get("user_id", "anonymous")
        if not self.space_id or not state.get("messages"):
            return

        session = MemorySession(
            space_id=self.space_id,
            actor_id=f"{self.actor_prefix}{user_id}",
            assistant_id=self.assistant_id
        )

        # 提取最后一轮用户-助手消息
        messages = state["messages"]
        turns = []
        for msg in messages[-2:]:
            role = "user" if msg.type == "human" else "assistant"
            turns.append(TextMessage(role=role, content=str(msg.content)[:2000]))
        if turns:
            session.add_messages(turns)
```

---

## 6. 部署配置

### 6.1 `agentarts_config.yaml`

```yaml
default_agent: personal-assistant

agents:
  personal-assistant:
    base:
      name: personal-assistant
      entrypoint: agent:app
      dependency_file: requirements.txt
      platform: linux/arm64
      language: python3
      base_image: python:3.10-slim
      region: cn-southwest-2

    swr_config:
      organization: personal-assistant-org
      repository: agent_personal_assistant
      organization_auto_create: true
      repository_auto_create: true

    runtime:
      invoke_config:
        protocol: HTTP
        port: 8080

      network_config:
        network_mode: PUBLIC
        # 如需 VPC 内访问，改为 PRIVATE 并配置 vpc_config

      identity_configuration:
        # === Inbound: Custom JWT (Google OAuth) ===
        authorizer_type: CUSTOM_JWT
        authorizer_configuration:
          custom_jwt:
            discovery_url: https://accounts.google.com/.well-known/openid-configuration
            allowed_audience:
              - "<your-google-oauth-client-id>"
            allowed_clients:
              - "<your-google-oauth-client-id>"
            allowed_scopes:
              - "openid"
              - "profile"
              - "email"
          # === Inbound: API Key (开发调试) ===
          key_auth:
            api_keys:
              - "opencode-dev-api-key-2026"

      observability:
        tracing:
          enabled: true
        metrics:
          enabled: true
        logs:
          enabled: true

      artifact_source:
        url: swr.cn-southwest-2.myhuaweicloud.com/personal-assistant-org/agent_personal_assistant:latest
        commands: []

      environment_variables:
        - key: MODEL_API_KEY
          value: "<MaaS API Key>"
        - key: MODEL_NAME
          value: "deepseek-v3.2"
        - key: MODEL_URL
          value: "https://api.modelarts-maas.com/openai/v1"
        - key: MEMORY_SPACE_ID
          value: "<Memory Space ID>"

      tags:
        - key: app
          value: personal-assistant
        - key: env
          value: dev
```

### 6.2 部署命令

```bash
# 本地开发
agentarts dev

# 部署到云端
agentarts launch

# 调用（API Key 模式）
agentarts invoke '{"message": "帮我查一下我的 GitHub Issues"}'

# 调用（JWT 模式，通过 HTTPS + Bearer Token）
curl -X POST https://<runtime-domain>/invocations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <Google_ID_Token>" \
  -d '{"message": "查一下我的日程"}'
```

---

## 7. 项目文件结构

```
personal-assistant/
├── .agentarts_config.yaml      # AgentArts 项目配置 + Runtime Identity 配置
├── app/
│   └── personal_assistant/
│       ├── __init__.py
│       ├── agent.py            # Agent 入口 + LangGraph 编排
│       ├── memory.py           # Memory 集成
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── github_tools.py # GitHub 工具 (OAuth2 User Federation)
│       │   ├── google_tools.py # Google 工具 (OAuth2 User Federation)
│       │   ├── internal_tools.py # 内部 API 工具 (API Key M2M)
│       │   └── cloud_tools.py  # 云资源工具 (STS M2M)
│       └── prompts/
│           └── system_prompt.txt
├── Dockerfile                  # ARM64 镜像构建
├── requirements.txt            # Python 依赖
└── README.md
```

---

## 8. Inbound / Outbound 认证矩阵

| 用户身份 | Inbound 方式 | Outbound 目标 | Outbound 方式 | Auth Flow |
|----------|-------------|---------------|---------------|-----------|
| Google 用户 | JWT (Google OAuth) | GitHub API | OAuth 2.0 | USER_FEDERATION |
| Google 用户 | JWT (Google OAuth) | Google Calendar | OAuth 2.0 | USER_FEDERATION |
| 企业员工 | JWT (Okta/Entra ID) | 内部 CRM | API Key | M2M |
| 运维人员 | JWT (Okta/Entra ID) | 云资源 | STS Token | M2M |
| 开发者 | API Key | _(全部)_ | _(开发调试)_ | — |

---

## 9. 参考文档

| 文档 | 路径 |
|------|------|
| AgentArts 平台参考 | `architecture/cloud-service/agentarts.md` |
| AgentCore 对比参考 | `architecture/cloud-service/agentcore.md` |
| Identity SDK 文档 | `https://support.huaweicloud.com/highcode-agentarts/agentarts_10_044.html` |
| Runtime 部署文档 | `https://support.huaweicloud.com/highcode-agentarts/agentarts_10_028.html` |
| 认证鉴权 | `https://support.huaweicloud.com/highcode-agentarts/agentarts_10_047.html` |
| Memory SDK 文档 | `https://support.huaweicloud.com/highcode-agentarts/agentarts_10_043.html` |
| SDK 快速开始 | `https://support.huaweicloud.com/highcode-agentarts/agentarts_10_040.html` |
