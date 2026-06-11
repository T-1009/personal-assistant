---
status: backlog
---

# Chore 3: 新增 Docs/Tests 维护工作流

在 `personal-assistant-meta/architecture/devops/opencode-workflow.md` 中新增一个文档与测试维护工作流（Maintenance Workflow），确保 docs 和 tests 与当前代码保持同步。过时的（stale）测试和文档应被更新或移除。

---

## 背景

当前 opencode-workflow.md 定义了完整的 Issue 驱动开发流程（Meta → Service/Client/Infra → E2E → Merge），但缺少一个系统性的维护机制来处理以下问题：

1. **文档漂移（Doc Drift）**：`specs/` 和 `architecture/` 下的文档随代码迭代逐渐过时，与实现不一致
2. **测试腐化（Test Rot）**：`personal-assistant-e2e/` 中的回归测试、各领域的单元/集成测试可能随着 feature 变更而失效或不再有意义
3. **孤儿文档/测试（Orphan Docs/Tests）**：已删除的功能对应的 specs、architecture 文档或测试文件未被清理

当前流程中，Tester 和 Reviewer 会在 per-issue 范围内处理 stale 测试（Reviewer 审计 Tester 移除的 stale 测试），但这只覆盖 **当前 Issue 触及的局部范围**，不覆盖以下场景：

- 跨 Issue 积累的 stale 产物（多个 feature 迭代后，某些早期测试/文档已无人记得）
- 未被任何 Issue 触发的文档-代码不一致（例如 API 签名变了但 specs 没更新）
- 发现 stale 产物后没有标准流程来决定「更新」还是「移除」

需要一个独立的 Maintenance Workflow，作为开发流程之外的周期性或触发式补充。

---

## 范围

### In Scope

- 在 `architecture/devops/opencode-workflow.md` 中新增一个章节，定义 docs/tests 维护工作流的触发条件、执行步骤和决策规则
- 工作流覆盖范围：
  - `personal-assistant-meta/specs/` — 功能规格文档
  - `personal-assistant-meta/architecture/` — 架构文档（含 ADR）
  - `personal-assistant-e2e/` — E2E 回归测试
  - 各领域内的单元/集成测试（`personal-assistant-service/tests/`、`personal-assistant-client/` 等）
- 定义 stale 判定标准（什么算 stale）
- 定义处置决策矩阵（更新 vs 移除的选择依据）

### Out of Scope

- 实现自动化 stale 检测工具（本 issue 只定义流程，工具化后续另开 issue）
- 修改现有 Agent 的 agent 文件（`.opencode/agents/*.md`）——如需新增 Agent 或调整权限，后续另开 feature

---

## 设计要点

### 1. 触发条件（二选一或并存）

| 触发方式 | 说明 | 适用场景 |
|---------|------|---------|
| **周期性触发** | 按固定节奏（如每 2 周 / 每月）执行一次全量 audit | 持续积累的 stale 产物 |
| **事件触发** | Feature 合入 main 后，触发一次增量 audit（仅检查本次变更波及的 docs/tests） | 紧耦合的及时同步 |

### 2. Stale 判定标准

| 产物类型 | Stale 判定 |
|---------|-----------|
| specs 文档 | 描述的功能已变更/移除，或 API 签名与实现不一致 |
| architecture 文档 | 组件/模块/数据流已重构，文档未更新 |
| ADR | 决策已被后续 ADR 推翻（superseded），但未标注 |
| E2E 测试 | 测试覆盖的 happy path 已不再存在，或测试持续 skip/fail 超过 N 天 |
| 单元/集成测试 | 测试的 target 函数/组件已删除或签名变更，测试无法运行 |

### 3. 处置决策矩阵

| 情况 | 决策 |
|------|------|
| 文档/测试对应的功能仍存在，但内容过时 | **更新**（update） |
| 文档/测试对应的功能已完全移除 | **移除**（remove） |
| 文档描述的是 to-be 目标，尚未实现 | **保留**，标注状态 |
| 测试因环境/依赖问题暂时不可运行（非代码问题） | **保留**，标注 known issue |
| 无法判断是否仍有用 | **标记为待确认**，上报 Human |

### 4. 执行者

维护工作流可以设计为：

- **方案 A**：复用现有 Agent（如 personal-assistant-e2e-tester 负责 E2E 测试 audit），由 personal-assistant-manager 统一调度
- **方案 B**：新增专门的 maintenance agent（如 `personal-assistant-maintenance-dev`），专注 docs/tests 同步

具体方案在 Implementation Plan 中确定，issue 只陈述需求。

---

## 产物

- `personal-assistant-meta/architecture/devops/opencode-workflow.md` 中新增 **"Docs & Tests Maintenance Workflow"** 章节，包含：
  - 触发条件
  - 执行步骤（含 Mermaid 流程图）
  - Stale 判定标准
  - 处置决策矩阵
  - 与其他工作流（开发流程、E2E Control Loop）的关系

---

## 验收标准

- [ ] `opencode-workflow.md` 包含新的 Maintenance Workflow 章节
- [ ] 章节明确定义了触发条件、stale 判定标准和处置决策
- [ ] 有 Mermaid 图描述工作流执行步骤
- [ ] Maintenance Workflow 与现有开发流程的关系清晰（不冲突、不重叠）
- [ ] 经 meta-reviewer 审查通过

---

## 参考

| 文档 | 路径 |
|------|------|
| OpenCode Workflow | `architecture/devops/opencode-workflow.md` |
| 总体架构 | `architecture/overall_architecture.md` |
| 总体功能规格 | `specs/overall_specifications.md` |
| E2E 测试目录 | `personal-assistant-e2e/AGENTS.md` |
