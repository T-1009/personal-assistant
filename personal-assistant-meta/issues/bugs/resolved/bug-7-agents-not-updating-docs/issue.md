---
status: backlog
---

# Bug 7: Agent 开发后未同步更新 AGENTS.md / README.md

Implementation 阶段完成后，相关目录的 `AGENTS.md` 和 `README.md` 未随代码变更同步更新，导致文档中的路由引用、架构描述、配置说明与实际代码不一致。

## 现象

Refactor 4（路由收敛）合并后发现以下文档存在陈旧引用，plan 中已明确列出但未被更新：

| 文件 | 陈旧引用数 | 类型 |
|------|:---:|------|
| Root `README.md` | 2 | Mermaid 架构图中路由路径 |
| `agentarts-deploy-runbook.md` | 12 | curl 命令、判定表、sequence diagram、checklist |
| `frontend_architecture.md` | 9 | Chainlit 挂载路径、容器路由图、健康检查示例 |
| `backend_architecture.md` | 1 | Gateway 路径示例 |

这些文件均在 plan 中明确标记为需修改，但 implementation 阶段没有被任何 agent 执行。

## 根因

```
┌─────────────────────────────────────────────────────────────┐
│ Plan 阶段                        Implementation 阶段          │
│                                                              │
│ meta-dev 列出需修改文件          service-dev → 只改 service/  │
│   ├── service/app/main.py  ✅    client-dev  → 只改 client/   │
│   ├── service/config.yaml  ✅    infra-dev   → 只改 infra/    │
│   ├── deploy-runbook.md    ❌                                  │
│   ├── frontend_arch.md     ❌    ← 谁来改 meta/ 的文档？       │
│   └── README.md            ❌                                  │
└─────────────────────────────────────────────────────────────┘
```

**核心问题**：`personal-assistant-meta/` 下的文档不属于 service / client / infra 任一 domain 的范围，三个 domain manager 都不会去更新它们。plan 列出了所有变更文件，但没有指派执行者，导致这些文档更新成为"三不管"地带。

具体来说：
1. **Domain 边界限制**：`service-dev` 只工作于 `personal-assistant-service/`，`client-dev` 只工作于 `personal-assistant-client/`，`infra-dev` 只工作于 `personal-assistant-infra/`。它们不会主动修改 `meta/` 下的文档。
2. **Plan 未指派执行者**：Implementation Plan 的 §3 列出了所有需修改的文件（含 meta/ 下的文档），但没有说明这些文件的修改由哪个 domain 负责。
3. **无文档同步检查步骤**：Pipeline 中没有"验证文档已更新"的 gate，文档陈旧只能在事后人工发现。

## 影响

- 新成员按 README 中的 Mermaid 图理解架构，看到的是过时路由
- 运维按 deploy runbook 中的 curl 命令验证部署，命令全部 404
- 累积效应：每次 refactor 都产生文档债，越来越难以清理

## 修复方向

### 选项 A：扩展 plan 格式 — 显式指派文档更新责任

在 Implementation Plan 的 §3（文件变更清单）中，为每个文件标注负责的 domain/agent：

```markdown
| 文件 | 变更 | 执行 agent |
|------|------|-----------|
| `service/app/main.py` | 路由迁移 | service-dev |
| `meta/architecture/.../deploy-runbook.md` | curl 命令更新 | meta-dev（在 plan 阶段同步完成） |
| `meta/architecture/frontend_architecture.md` | 路径更新 | meta-dev |
```

**优点**：最小的流程变更，plan 写清楚谁做什么。
**缺点**：依赖 plan 质量，遗漏仍可能发生。

### 选项 B：在 Pipeline 中增加文档一致性检查 gate

在 E2E 通过后、Merge Approval 前，增加一个文档检查步骤——扫描所有 `*.md` 文件中的路由/API/配置引用，与当前代码实际注册的路由做交叉验证。

**优点**：自动化，不依赖人工记忆。
**缺点**：实现复杂度高（需要解析 FastAPI 路由表 + 扫描 markdown 中的 URL 模式）。

### 选项 C：meta-dev 在 plan 阶段直接完成文档更新

将文档更新从 implementation 阶段前移到 plan 阶段——meta-dev 在写 plan 的同时，直接把 meta/ 下的架构文档、runbook、README 更新好。这样文档变更与 plan 一起提交（plan commit），实现代码在后续并行阶段进行。

**优点**：文档与设计同步，不依赖 implementation agent。
**缺点**：如果 implementation 阶段发现 plan 需要调整，文档可能也需要修正。

### 推荐

**A + C 组合**：
1. **Plan 阶段的文档更新**（meta-dev 职责）：meta-dev 在写 plan 时同步更新 `meta/architecture/` 和 root `README.md` 中受影响的文档——这些文件描述的是"系统应该长什么样"，应在设计阶段就确定。
2. **Plan 文件清单显式标注**：plan 中 §3 文件清单为每个文件标注 `agent: meta-dev | service-dev | client-dev | infra-dev`，确保没有"三不管"文件。

## 其他考量

- `ADR/` 目录下的 ADR 文件是历史决策记录，**不纳入此 scope**——ADR 记录的是决策时的上下文，不随后续变更回溯修改。
- `issues/` 下的 resolved issue 和 plan 同样是历史记录，不修改。
- 各 domain 的 `AGENTS.md`（如 `personal-assistant-service/AGENTS.md`）由各 domain manager 负责在其 control loop 中检查是否需要更新。此 bug 主要针对 meta 层（跨 domain 的架构文档和 README）。

## 参考

- Refactor 4: `../refactor/refactor-4-consolidate-invocations-routes/issue.md`
- Refactor 4 plan: `../refactor/refactor-4-consolidate-invocations-routes/plan.md`（§3 文件清单列出了文档变更但未标注执行 agent）
- Pipeline 流程: `../../AGENTS.md`
