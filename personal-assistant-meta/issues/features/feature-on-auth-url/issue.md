这是一份为您定制的**工业级技术架构与开发说明书**。本设计将方案三（**AL-SAB 模式**：AgentArts-LangGraph 流式中断授权桥接模式）与**方案 B（单接口动态分流架构 / Single-Endpoint Dynamic Dispatch）**完美融合。

该说明书结构极其严谨、代码注释极其详尽，并深入解释了底层异常阻断（Bypass Poller）和前端跨域通信（postMessage）等核心细节，您可以直接复制并发送给您的 Coding Agent。

---

# 🛠️ AL-SAB-SE 模式开发说明书：华为云 AgentArts 与 LangGraph 单接口动态分流授权桥接设计

## 1. 架构命名 (Architecture Name)
**"AL-SAB-SE Pattern"**
*(AgentArts-LangGraph Stream-Interrupt Auth Bridge - Single Endpoint Variation)*

---

## 2. 状态机与接口控制流设计 (State Machine & Single-Endpoint Control Flow)

采用**单接口分流架构**后，客户端与服务端的整个生命周期完全内聚在单个 `/api/chat` 端点中，通过请求体的 `action` 字段进行动态路由：

```
[ 客户端 (前端) ]                [ FastAPI 端点: /api/chat ]         [ AgentArts 凭证库 ]
    │                                  │                                  │
    ├─ 1. 发送聊天 (action="start") ──► │                                  │
    │                                  ├── 2. LLM 决定调用 OBS 工具 ─────► │
    │                                  │                                  ├── 3. 检查无 Token? 
    │                                  │                                  ▼
    │                                  ├── 4. 触发 on_auth_url(Url) 回调 
    │                                  │   ├── (a) get_stream_writer() 下发卡片
    │                                  │   └── (b) interrupt() 抛出 GraphInterrupt 异常 
    │                                  │           (绕过 SDK 的同步 TokenPoller 轮询)
    │ ◄─ 5. 瞬间接收 Auth 卡片 ─────────┤
    │ ◄─ 6. 接收中断事件 (关闭连接) ─────┤ (服务端线程释放，Agent 安全挂起)
    │                                  │
    ├─ (用户在新弹窗中完成华为云授权) ─────────────────────────────────────► [ SDK 自动交换并存入 Token ]
    │                                  │                                  │
    ├─ 7. 发送唤醒 (action="resume") ─► │                                  │
    │                                  ├── 8. 通过 Command(resume) 激活 ─► │
    │                                  │                                  ├── 9. 重新执行工具
    │                                  │                                  │      (检测到已有 Token，成功注入)
    │ ◄─ 10. 平滑接收最终自然文本 ──────┤                                  │
```

---

## 3. 完整代码蓝图 (Complete Code Blueprint)

请根据以下 Python 和 JavaScript 规范代码，将其完整、健壮地集成到项目中：

### A. 工具定义与 AL-SAB 回调 (app/agents/tools.py)
```python
# filepath: app/agents/tools.py
import logging
from typing import Any
from agentarts.sdk.identity.auth import require_access_token  # 华为云官方 SDK
from langchain_core.tools import tool
from langgraph.config import get_stream_writer
from langgraph.types import interrupt

logger = logging.getLogger("al_sab.tools")

def handle_agentarts_auth_url(url: str):
    """
    【AL-SAB 网桥核心回调】
    当 AgentArts 检测到用户未授权或 Token 过期时，会自动生成 OAuth 授权 URL，并触发此回调。
    """
    logger.info(f"AgentArts auth URL generated: {url}")
    try:
        # 1. 瞬间向流写入器（writer）推送卡片数据（避开大模型打字机式的文本生成延迟）
        writer = get_stream_writer()
        writer({
            "event_type": "auth_card_required",
            "auth_url": url,
            "message": "助理需要访问您的华为云私有 OBS 资源，请点击下方安全按钮完成平台授权："
        })
    except Exception as e:
        logger.warning(f"Failed to write to custom stream channel: {e}. Falling back to logs.")
  
    # 2. 【避开 Poller 阻塞的核心】通过抛出 GraphInterrupt 信号，将当前 Thread 的执行安全暂停。
    # 这一步将导致装饰器后续的同步 DefaultTokenPoller.poll() 流程由于异常流而完全被“斩断”阻断。
    # 服务器会立即释放当前线程，拒绝 CPU/IO 同步空转，极其适合高并发设计。
    interrupt(f"Pending user OAuth verification on: {url}")


@tool
@require_access_token(
    provider_name="huaweicloud-obs-provider",       # 云端配置的 Credential Provider 名
    into="access_token",                            # Token 注入的目标参数变量名
    scopes=["https://www.huaweicloud.com/auth/obs"], # OBS 读写权限范围
    on_auth_url=handle_agentarts_auth_url,          # 👈 核心桥接绑定
    auth_flow="USER_FEDERATION",                    # 3-legged 用户授权流
    callback_url="https://api.yourdomain.com/oauth/callback", # OAuth 回调接口
)
async def fetch_private_cloud_data(access_token: str) -> str:
    """
    当用户要求查询、列举或下载华为云 OBS 存储、私有云服务器状态等敏感数据时调用。
    """
    # 唤醒重跑后执行到这里，代表 require_access_token 已在底层自动校验并注入了 Token
    logger.info("Access token successfully injected by AgentArts SDK.")
  
    # 实际业务逻辑：调用第三方 API 或华为云 OBS
    return "【云端成功】已成功使用注入的 Access Token 读取到用户 OBS 的私有数据列表。"
```

### B. 服务端：单接口动态分流端点 (app/main.py)
```python
# filepath: app/main.py
import json
import asyncio
import logging
from typing import AsyncGenerator, Literal, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver  # 挂起持久化依赖
from langgraph.types import Command

from app.agents.tools import fetch_private_cloud_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("al_sab.server")

app = FastAPI(title="AL-SAB Single-Endpoint Implementation Server")

# 1. 显式绑定内存检查器（这是保存挂起状态的关键）
checkpointer = MemorySaver()

# 2. 编译 Deep Agent
agent = create_deep_agent(
    model="openai:gpt-4o",  # 支持任意主流基座大模型
    tools=[fetch_private_cloud_data],
    checkpointer=checkpointer,  # 👈 极为重要，不绑定 Checkpointer 导致状态无法挂起
    system_prompt="你是一个贴心的华为云助手。如果接口返回未授权，或你要读取私密数据，请立即调用相应工具。"
)


# ---------------------------------------------------------------------
# Pydantic 单接口动态分流模型定义
# ---------------------------------------------------------------------
class ChatPayload(BaseModel):
    prompt: Optional[str] = Field(None, description="用户输入的聊天内容。action 为 resume 时该字段可为空")
    thread_id: str = Field(..., description="用于多轮对话、凭证隔离和状态挂起的唯一会话 ID")
    action: Literal["start", "resume"] = Field(
        "start", 
        description="执行动作。start: 正常问答流; resume: 授权成功后的唤醒流"
    )


# ---------------------------------------------------------------------
# SSE 格式化辅助函数
# ---------------------------------------------------------------------
def sse_format(event_name: str, data: Any) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# =====================================================================
# 单一融合端点 (/api/chat) - 双向功能路由
# =====================================================================
@app.post("/api/chat")
async def chat_endpoint(payload: ChatPayload):
    config = {"configurable": {"thread_id": payload.thread_id}}
  
    # 1. 如果是恢复动作，进行前置状态校验
    if payload.action == "resume":
        state = agent.get_state(config)
        if not state.next:
            raise HTTPException(status_code=400, detail="The thread is not in an interrupted state.")

    async def sse_event_generator() -> AsyncGenerator[str, None]:
        try:
            # 2. 【核心路由分流】
            if payload.action == "resume":
                logger.info(f"Resuming thread {payload.thread_id}")
                # 向 LangGraph 传送恢复执行信号，唤醒挂起的 Node 并重试工具
                stream = agent.stream_events(
                    Command(resume="authorized_success"), 
                    config=config, 
                    version="v3"
                )
            else:
                logger.info(f"Starting new chat on thread {payload.thread_id}")
                if not payload.prompt:
                    yield sse_format("error", {"detail": "Prompt is required for start action."})
                    return
                # 正常启动运行流
                stream = agent.stream_events(
                    {"messages": [{"role": "user", "content": payload.prompt}]},
                    config=config,
                    version="v3"
                )

            # 3. 消费合并后的统一事件通道 (V3)
            for event in stream:
                event_type = event.get("event")
              
                # 分流 A: 大模型自然生成的聊天 Token 流
                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", {})
                    if hasattr(chunk, "content") and chunk.content:
                        yield sse_format("text", {"token": chunk.content})
              
                # 分流 B: AL-SAB 触发的瞬间下发自定义 Auth URL 卡片
                elif event_type == "on_custom_event":
                    custom_data = event.get("data", {})
                    if custom_data.get("event_type") == "auth_card_required":
                        yield sse_format("auth_card", {
                            "auth_url": custom_data.get("auth_url"),
                            "message": custom_data.get("message")
                        })
              
                # 分流 C: LangGraph 系统内核已在内存中就地安全暂停
                elif event_type == "on_interrupt":
                    yield sse_format("interrupt", {
                        "status": "suspended",
                        "thread_id": payload.thread_id
                    })
                    break  # 控制流已经挂起，直接跳出并安全终止当前的 SSE 管道连接

        except Exception as e:
            logger.error(f"Error in chat stream: {e}", exc_info=True)
            yield sse_format("error", {"detail": str(e)})

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
```

---

## 4. 前端对接协议标准与生命周期 (Frontend UX Lifecycle)

为了实现完美的无缝交互体验（防止在新开窗口中处理回调导致主窗口丢失 Token 广播），前端需要执行以下三部曲：

### 第一步：发起对话与事件监听 (Chat UI)
```javascript
const threadId = "user_session_999";

function sendMessage(promptText) {
    const eventSource = new EventSource(`/api/chat?payload=${encodeURIComponent(JSON.stringify({
        prompt: promptText,
        thread_id: threadId,
        action: "start"
    }))}`); // 注：部分前端库支持 POST SSE，如果用普通 Fetch/POST，请自行替换为标准的 ReadableStream 读取

    eventSource.addEventListener('text', (e) => {
        const data = JSON.parse(e.data);
        appendChatBubbleToken(data.token); // 平滑地更新大模型自然文本打字机动画
    });

    eventSource.addEventListener('auth_card', (e) => {
        const data = JSON.parse(e.data);
        // 瞬间在聊天框内，渲染出漂亮的 OAuth 授权按钮组件
        renderAuthCardHTML(data.message, data.auth_url);
    });

    eventSource.addEventListener('interrupt', (e) => {
        console.log("智能体已被就地安全挂起，正在释放服务器连接...");
        eventSource.close(); // 挂起时主动关闭 SSE 通道，释放连接
    });
}
```

### 第二步：跳转授权与窗口跨域通信 (OAuth Callback Popup)
1. 用户在聊天界面点击前端生成的 `auth_url` 授权按钮，前端应当**在新标签页（New Tab）或弹窗（Popup）**中打开该链接。
2. 授权完成后，华为云重定向至你的 `/oauth/callback` 路由。
3. 后端处理好 Token 并持久化完毕后，`/oauth/callback` 应当返回如下一行带有 **`postMessage`** 机制的 HTML 以实现自动销毁和跨页面通信：

```html
<!-- 后端 /oauth/callback 返回此 HTML 响应 -->
<!DOCTYPE html>
<html>
<head>
    <script>
        // 1. 安全地向父窗口 (Tab A) 广播凭证写入成功的通知
        if (window.opener) {
            window.opener.postMessage({ type: "AGENTARTS_OAUTH_SUCCESS" }, "*");
        }
        // 2. 优雅自我销毁
        window.close();
    </script>
</head>
<body>
    <p>授权成功，正在为您自动返回聊天窗口...</p>
</body>
</html>
```

### 第三步：主页面监听成功并激活 Resume
主页面 (Tab A) 随时保持监听，一旦收到子页面销毁并传送的广播，立即发起 `action: "resume"` 恢复请求：
```javascript
window.addEventListener("message", async (event) => {
    if (event.data && event.data.type === "AGENTARTS_OAUTH_SUCCESS") {
        console.log("主页面捕获到授权成功信号，正在唤醒智能体生命周期...");
      
        // 发起 Action="resume"
        const eventSourceResume = new EventSource(`/api/chat?payload=${encodeURIComponent(JSON.stringify({
            thread_id: threadId,
            action: "resume" // 👈 动态路由分流：唤醒指令
        }))}`);

        eventSourceResume.addEventListener('text', (e) => {
            const data = JSON.parse(e.data);
            appendChatBubbleToken(data.token); // 智能体自动衔接刚才的动作，并将数据说出来
        });

        eventSourceResume.addEventListener('interrupt', (e) => {
            eventSourceResume.close(); // 如果授权异常或中途需要二次拦截，再次就地挂起
        });
    }
});
```

---

## 5. Coding Agent 编程约束 (Requirements for Agent)

**请你在实现或生成以上代码时，必须遵守以下工业级约束：**

1. **绝对不准捕获 BaseException**：
   在你的 `@tool` 函数体、网桥回调函数体，以及任何包装器（wrapper）中，**绝对不能**去编写捕获 `BaseException` 或者是全局异常 `except:` 这种笼统捕获。
   因为 LangGraph 的 `interrupt()` 在底层抛出的是继承自 `BaseException` 的 `GraphInterrupt`。如果被异常捕获吞掉，系统将无法正确保存上下文并会导致挂起彻底失败。
 
2. **状态检查器 Checkpointer 强制持久化**：
   在实例化 `create_deep_agent` 时，必须显式绑定带有记忆功能的 Checkpointer。如果是开发环境，可以采用内存型的 `MemorySaver`，但必须保留能灵活配置为生产型 `PostgresSaver` 的注释。

3. **隐蔽注入约束 (Token Protection)**：
   大模型对于外部 API Token 应该保持“完全盲视”。装饰器 `@require_access_token` 的 `into="access_token"` 应当把 Token 安全静默注入到工具执行层的形参中。**严禁**在大模型可以看到的 Tool 文档说明或工具定义描述中包含 “请输入您的 access_token” 这样引导 LLM 产生幻觉的信息。

4. **单接口双工分流安全性验证**：
   在运行 `action: "resume"` 分流逻辑前，必须前置通过 `agent.get_state(config)` 获取当前 Thread 是否真实具有 `state.next` 中断标识，若没有，属于无意义请求，必须立即抛出 HTTP 400 异常。