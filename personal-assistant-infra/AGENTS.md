# AGENTS.md

> 本文件是 **personal-assistant-infra** 目录的专用 instructions，仅适用于该目录下的相关工作。

## Directory Guide

`personal-assistant-infra/` 是系统的**基础设施即代码（IaC）**目录，管理 `agentarts_config.yaml` 管不到的华为云基础资源。技术选型见 [ADR-006](../personal-assistant-meta/architecture/ADR/ADR-006-iac-cdktf-typescript.md)。

开始前先阅读项目根目录的 [`AGENTS.md`](../AGENTS.md) 了解整体项目结构和规范。

### 设计文档

所有架构设计、ADR 和变更规划在 `personal-assistant-meta/` 中：

| 文档 | 内容 |
|------|------|
| `architecture/devops/cicd.md` | CI/CD 流水线、分层部署策略、IaC 触发时机 |
| `architecture/ADR/ADR-006-iac-cdktf-typescript.md` | CDKTF 选型理由、技术对比、目录结构 |
| `issues/features/feature-9-deployment/issue.md` | 部署上线任务（含 IaC 相关子任务） |

### 与 `agentarts_config.yaml` 的关系

两者互不冲突，管不同层的资源：

```
personal-assistant-service/.agentarts_config.yaml  → AgentArts 层（容器/认证/可观测）
personal-assistant-infra/**/*.ts                    → 华为云基础资源层（OBS/RDS/IAM/VPC/EIP/CDN）
```

## 技术栈

| 项 | 选择 | 依据 |
|----|------|------|
| **IaC 框架** | CDK for Terraform (CDKTF) | ADR-006 |
| **语言** | TypeScript | 编译期类型检查、IDE 支持、团队经验匹配 |
| **Provider** | `@cdktf-provider-huaweicloud` | HuaweiCloud Terraform Provider |
| **包管理** | npm | CDKTF 生态标准 |
| **测试** | Jest / Vitest | CDKTF 单元测试 |

## 目录结构

```
personal-assistant-infra/
├── AGENTS.md               # 本文件
├── README.md               # 快速开始与运维手册
├── main.ts                 # CDKTF 入口（App + Stack 注册）
├── stacks/
│   └── pa-stack.ts         # PersonalAssistantStack — 主 Stack
├── constructs/             # 可复用 Construct（可选，复杂资源抽取）
├── package.json            # cdktf + provider 依赖
└── tsconfig.json           # TypeScript 配置
```

## 触发时机

以下场景出现任意一个，就需要在 `personal-assistant-infra/` 中编写 IaC：

| 场景 | 需要的资源 |
|------|-----------|
| Web Chat 前端需要静态托管 | OBS Bucket + CDN 加速域名 |
| 用户-渠道 ID 映射需要持久化存储 | RDS（PostgreSQL） |
| OfficeClaw 需要固定公网入口 | EIP + 带宽配置 |
| Identity STS Provider 需要授权 | IAM Agency / Role / Policy |
| Web Chat 需要 HTTPS | SSL 证书 + WAF / ELB |

## 常用命令

```bash
# 安装依赖
cd personal-assistant-infra && npm install

# 生成 Terraform JSON（检查语法和类型）
npx cdktf synth

# 查看变更计划
npx cdktf diff

# 执行部署
npx cdktf deploy

# 运行测试
npm test
```

## 开发约定

- **Stack 命名**：一个环境一个 Stack（如 `pa-stack`），通过 `context` 区分 dev/staging/prod
- **Resource 命名**：使用 kebab-case，带 `pa-` 前缀避免与平台资源冲突
- **敏感信息**：禁止硬编码，通过环境变量或 Terraform variables 注入（标记 `sensitive = true`）
- **状态管理**：Terraform state 存储在 OBS backend（`pa-terraform-state` bucket），避免本地状态丢失
- **Outputs**：跨 Stack 引用使用 Stack Outputs，供 Service 配置读取（如 RDS endpoint、OBS bucket name）
- **变更流程**：修改 IaC → `cdktf synth`（本地验证）→ `cdktf diff`（查看变更）→ PR Review → `cdktf deploy`
