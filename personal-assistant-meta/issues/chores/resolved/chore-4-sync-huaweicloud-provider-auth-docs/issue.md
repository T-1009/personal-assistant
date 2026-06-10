# 同步 HuaweiCloud Provider 原生环境变量认证文档

## Motivation

Commit `4547c81e39b2f300c0e5660e50000e9b0c9a5476` 将华为云认证从自定义 `TF_VAR_ak`/`TF_VAR_sk` 变量切换为 Provider 原生 `HW_ACCESS_KEY`/`HW_SECRET_KEY` 环境变量。代码侧（`main.tf`、`variables.tf`、CI workflow）变更已完成，但以下文档和注释未同步更新，仍引用旧认证方式，导致：

- 新开发者按文档操作会使用已失效的 `terraform.tfvars` / `TF_VAR_ak` 配置方式，遇到 `Unsupported variable` 错误
- Architecture baseline 中的 Provider 示例与实际 `main.tf` 不一致（documentation drift）
- 本地留存旧 `terraform.tfvars` 的开发者执行 `tofu plan` 会收到 undeclared variable 警告

## Scope

### 在范围内（7 个文件）

| # | 文件 | 过期内容 | 域名 |
|---|------|---------|------|
| 1 | `personal-assistant-infra/variables.tf` (L1-5) | 头部注释引用 `ak`/`sk`、`TF_VAR_ak`/`TF_VAR_sk` | infra |
| 2 | `personal-assistant-infra/README.md` (L16, L41-50, L81) | 前置条件、部署示例、目录树均引用旧方式 | infra |
| 3 | `personal-assistant-infra/AGENTS.md` (L46, L80, L98) | 目录树标注 `ak, sk, region`；敏感信息约定引用 `TF_VAR_*` | infra |
| 4 | `personal-assistant-infra/outputs.tf` (L21-22) | 注释引用 `terraform.tfvars` 和 `TF_VAR_*` | infra |
| 5 | `personal-assistant-meta/architecture/devops/cicd.md` (L200-203) | §4.4 Provider HCL 示例含 `access_key = var.ak` / `secret_key = var.sk` | meta |
| 6 | `personal-assistant-meta/architecture/devops/agentarts-deploy-runbook.md` (L542-543, L547, L582, L589) | Provider 示例和凭据说明仍引用旧方式 | meta |
| 7 | `personal-assistant-meta/architecture/ADR/ADR-006-iac-cdktf-typescript.md` (L89, L111-112) | 目录树和 Provider 示例含旧认证方式；建议添加 amendment 记录变更 | meta |

### 不在范围内

- ❌ `personal-assistant-infra/main.tf` / `obs.tf` — 代码行为已正确
- ❌ `.github/workflows/deploy-infra.yml` — CI 环境变量已更新
- ❌ `refactor-6-migrate-cdktf-to-opentofu-hcl/` 下所有文件 — 历史归档记录，不追溯修改（与 bug-7 原则一致）
- ❌ 本地 `terraform.tfvars` — gitignored 文件，不提交；在 issue 中提醒开发者手动清理

## Acceptance Criteria

### Infra 文档更新
- [ ] `personal-assistant-infra/variables.tf` 头部注释不再提及 `ak`/`sk`、`TF_VAR_ak`/`TF_VAR_sk`，改为说明 `region` 变量及 Provider credentials 通过 `HW_ACCESS_KEY`/`HW_SECRET_KEY` 注入
- [ ] `personal-assistant-infra/README.md` 前置条件、部署示例（L41-50）全部替换为 `export HW_ACCESS_KEY="..."` / `export HW_SECRET_KEY="..."` 方式；目录树中 `variables.tf` 说明更新为 `变量声明（region）`
- [ ] `personal-assistant-infra/AGENTS.md` 目录树说明更新；开发约定中敏感信息注入方式更新为 Provider 原生环境变量
- [ ] `personal-assistant-infra/outputs.tf` L21-22 过期凭据注释已删除或更新为当前认证方式

### Architecture 文档更新
- [ ] `personal-assistant-meta/architecture/devops/cicd.md` §4.4 Provider HCL 示例移除 `access_key = var.ak` / `secret_key = var.sk`，与 `main.tf` 实际内容一致
- [ ] `personal-assistant-meta/architecture/devops/agentarts-deploy-runbook.md` Provider 示例、凭据配置说明同步更新为 `HW_ACCESS_KEY`/`HW_SECRET_KEY`
- [ ] `personal-assistant-meta/architecture/ADR/ADR-006-iac-cdktf-typescript.md` Provider 示例更新；添加 amendment 记录认证方式已于 2026-06-10 改为 Provider 原生 `HW_*` 环境变量

### 完整性验证
- [ ] 在 `personal-assistant-infra/` 目录下执行 `tofu validate` 通过
- [ ] `tofu fmt -check` 通过（不涉及 `.tf` 代码变更，但格式一致性验证）
- [ ] 全文搜索 `TF_VAR_ak`、`TF_VAR_sk`、`access_key = var.ak`、`secret_key = var.sk` 在 `personal-assistant-infra/` 和 `personal-assistant-meta/architecture/` 的非历史文档中不再出现

## Notes

### 风险提示

1. **本地 `terraform.tfvars` 残留**：如果本地 `personal-assistant-infra/terraform.tfvars` 中仍包含 `ak = "..."` / `sk = "..."`，执行 `tofu plan` 会产生 `Warning: Values for undeclared variables`。开发者需手动删除这些项，改用 `export HW_ACCESS_KEY` / `HW_SECRET_KEY`。

2. **`obsutil` 仍使用 `HUAWEICLOUD_SDK_AK`/`HUAWEICLOUD_SDK_SK`**：本次变更仅针对 OpenTofu Provider 认证。`obsutil` 等华为云 CLI 工具仍使用 `HUAWEICLOUD_SDK_AK` / `HUAWEICLOUD_SDK_SK` 环境变量，不要误删。文档更新时需明确各工具的凭据作用域。

3. **Shell profile 残留**：开发者 `~/.zshrc` / `~/.bashrc` 中如有 `export TF_VAR_ak=...` / `export TF_VAR_sk=...`，虽不会导致 OpenTofu 报错（未被引用的环境变量静默忽略），但建议替换为 `HW_ACCESS_KEY` / `HW_SECRET_KEY`。

### Agent 指派建议

此 issue 涉及两个 domain 的文件，建议 Implementation Plan 中明确指派：
- `personal-assistant-infra/` 下 4 个文件 → **infra-dev** agent
- `personal-assistant-meta/architecture/` 下 3 个文件 → **meta-dev** agent

这直接解决了 bug-7 中识别出的"跨 domain 文档三不管"问题——两个 agent 各自在其领域内完成文档同步。

## Affected Architecture Docs
- personal-assistant-meta/architecture/devops/cicd.md
- personal-assistant-meta/architecture/devops/agentarts-deploy-runbook.md
- personal-assistant-meta/architecture/ADR/ADR-006-iac-cdktf-typescript.md
