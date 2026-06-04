---
status: backlog
---

# Epic 2: Memory 集成

本 Phase 集成 AgentArts Memory，实现跨 Session 的用户记忆：对话保存、上下文检索、长期记忆（偏好/事实/情景）的自动管理。

---

## 背景

当前 Agent 每次对话都是 "失忆" 的 —— 不记得用户之前说过什么。本 Phase 接入 AgentArts Memory SDK，使 Agent 能够在每次对话开始时加载用户的历史偏好和上下文，对话结束时保存本轮交互。

## 范围

- 创建 Memory Space（AgentArts 控制台）
- `app/memory.py` — Memory 集成模块
- Agent 处理逻辑中注入 Memory 上下文
- 对话结束后保存交互到 Memory
- 验证跨 Session 记忆

## 不涉及

- Memory 策略调优（先用默认配置）
- 记忆手动管理功能（如 "忘记我上次说的..."）

## 任务拆解

### 2.1 Memory Space 创建

- [ ] 在 AgentArts 控制台创建 Memory Space
- [ ] 获取 Space ID
- [ ] 配置环境变量 `MEMORY_SPACE_ID`

### 2.2 Memory 集成模块

- [ ] `app/memory.py` — PersonalAssistantMemory 类
  - `__init__`: 读取 `MEMORY_SPACE_ID`，初始化 actor_prefix 和 assistant_id
  - `get_context(user_id)` → 搜索长期记忆（偏好/语义/情景），返回拼接后的上下文字符串
  - `save_interaction(user_id, query, response)` → 保存最后一轮对话到 Memory
- [ ] 依赖：`agentarts.sdk.memory`（MemorySession、TextMessage、MemorySearchFilter）

### 2.3 Agent 处理逻辑改造

- [ ] `agent_handler.py` 中 `handle()` 方法
  - 调用 LLM 前：`memory_ctx = await memory.get_context(user_id)`
  - 将 `memory_ctx` 注入 AgentState 的 context 字段
  - LLM 返回后：`await memory.save_interaction(...)`
- [ ] system prompt 中增加 Memory 使用说明（"你拥有用户的偏好和对话历史,请参考..."）

### 2.4 验证

- [ ] 第一轮对话：用户说 "我喜欢简洁的回答"
- [ ] 第二轮对话（新 Session）：用户说 "帮我查下日程"，Agent 回答风格应偏简洁
- [ ] 记忆生成有约 30s 延迟，验证时需等待

## 依赖

- Epic 1（Agent 骨架）完成

## 参考

- ADR-003: AgentArts 平台
- `architecture/overall_architecture.md` #6 Memory 集成
- `architecture/devops/local-development.md` #3 Memory 开发说明
