# Personal Assistant Infra

CDKTF + TypeScript 管理华为云基础资源。Provider 为 `huaweicloud/huaweicloud`（v1.92+），通过 `cdktf get` 生成本地 TypeScript bindings。

## 管理的资源

| Resource | Type | Name | Region | Config |
|----------|------|------|--------|--------|
| OBS Bucket | `huaweicloud_obs_bucket` | `personal-assistant-web-chat` | `cn-southwest-2` | ACL=public-read, versioning=true, static website hosting (SPA: error_document=index.html) |

> 更多资源（RDS、IAM、VPC、EIP、CDN）将随项目增长逐步添加。

## 前置条件

- **Node.js** ≥ 18，**npm** ≥ 9
- **HuaweiCloud credentials**：`HUAWEICLOUD_SDK_AK` / `HUAWEICLOUD_SDK_SK` 环境变量
- **IAM 权限**：OBS FullAccess（当前必需），SWR FullAccess（后续使用）
- **Terraform CLI**：用于 provider bindings 生成（`cdktf get`），部署本身不直接依赖

## 快速开始

```bash
cd personal-assistant-infra

# 安装依赖
npm install

# 生成/更新 provider bindings（首次或 provider 版本变更时）
npx cdktf get
```

## 验证

```bash
# TypeScript 类型检查
npx tsc --noEmit

# 生成 Terraform JSON → cdktf.out/
npx cdktf synth

# 运行单元测试（Jest + cdktf snapshot）
npm test
```

## 部署

```bash
# 1. 配置华为云凭据
export HUAWEICLOUD_SDK_AK="<your-ak>"
export HUAWEICLOUD_SDK_SK="<your-sk>"

# 2. 预览变更计划
npx cdktf diff

# 3. 执行部署
npx cdktf deploy
```

## 销毁

```bash
# ⚠️ 删除 OBS bucket 及所有内容。生产环境慎用。
npx cdktf destroy
```

## 部署后快速验证

```bash
# 静态网站主页可访问
curl -sI https://personal-assistant-web-chat.obs-website.cn-southwest-2.myhuaweicloud.com/index.html
# Expected: HTTP 200

# SPA 路由回退（关键测试）
curl -sI https://personal-assistant-web-chat.obs-website.cn-southwest-2.myhuaweicloud.com/chat
# Expected: HTTP 200（非 404）
```

## 目录结构

```
personal-assistant-infra/
├── main.ts                 # CDKTF App entry point
├── stacks/
│   ├── pa-stack.ts         # PersonalAssistantStack — OBS bucket + provider
│   └── __tests__/
│       └── pa-stack.test.ts # Unit tests (Jest + cdktf snapshot)
├── constructs/
│   └── .gitkeep            # Placeholder for future reusable constructs
├── package.json            # cdktf + constructs + devDependencies
├── tsconfig.json           # TypeScript config (ES2022, commonjs, strict)
├── cdktf.json              # CDKTF provider config (huaweicloud/huaweicloud)
├── jest.config.js          # Jest config (ts-jest preset)
├── .gitignore              # Excludes cdktf.out/ .gen/ coverage/ node_modules/ dist/
├── AGENTS.md               # IaC 开发规范
└── README.md               # 本文件
```

> `cdktf.out/`、`.gen/`、`coverage/`、`node_modules/`、`dist/` 为构建产物，已通过 `.gitignore` 排除。

## 相关文档

| 文档 | 说明 |
|------|------|
| [Chore-1 部署 Runbook](../personal-assistant-meta/issues/chores/chore-1-agentarts-deploy/plan.md) | 首次部署操作手册（含 OBS Bucket 创建 §12） |
| [ADR-006 IaC 选型](../personal-assistant-meta/architecture/ADR/ADR-006-iac-cdktf-typescript.md) | CDKTF + TypeScript 技术决策 |
| [Overall Architecture](../personal-assistant-meta/architecture/overall_architecture.md) | 系统整体架构 |
| [Infra AGENTS.md](./AGENTS.md) | IaC 开发约定与规范 |

## 已知限制

- **Terraform state 为本地存储**：OBS backend（`pa-terraform-state` bucket）为最终目标，但需要预置 state bucket（chicken-and-egg 问题）。首次部署后迁移。见 `stacks/pa-stack.ts` 中的 TODO 注释及 runbook §19。
- **无 CI/CD 集成**：当前部署为手动 CLI 操作。CI pipeline 集成见 `cicd.md`。
