# ADR-006: 基础设施即代码（IaC）工具选型

> 状态：Accepted | 日期：2026-06-03

---

## 背景

Personal Assistant 涉及两类基础设施资源：

| 层 | 资源 | 管理工具 |
|------|------|----------|
| Agent 运行时层 | Runtime 容器、Memory Space、Identity Provider、网络模式、认证配置 | 需要选 |
| 华为云基础资源层 | OBS、RDS、EIP、IAM、CDN（未来需要时） | 需要选 |

需要为每层选定 IaC 工具。

## 决策

### Layer 1：AgentArts 层 → `agentarts_config.yaml`

AgentArts 平台原生提供的声明式配置文件。它已经是一份 IaC 模板：

- 声明容器配置（base image、entrypoint、端口、架构）
- 声明认证方式（JWT / API Key）
- 声明可观测性（Tracing / Metrics / Logging）
- 声明环境变量和网络模式

执行 `agentarts launch` 等同于 `terraform apply`。**不需要额外交替工具。**

### Layer 3：华为云基础资源层 → CDK for Terraform (CDKTF)，语言 TypeScript

当项目需要 `agentarts_config.yaml` 管不到的华为云资源时，使用 CDKTF + TypeScript 编写基础设施代码。

选择依据：

| 因素 | CDKTF (TypeScript) | Terraform HCL | RFS |
|------|-------------------|---------------|-----|
| **语言** | TypeScript（通用编程语言） | HCL（DSL） | HCL（同 Terraform） |
| **类型安全** | ✅ 编译期检查 | ❌ `terraform plan` 阶段 | ❌ |
| **抽象能力** | ✅ 类、函数、接口、循环 | ⚠️ 仅 module + count/for_each | ⚠️ 同 Terraform |
| **IDE 支持** | ✅ 自动补全、跳转、重构 | ⚠️ Terraform LSP 有限 | ❌ 控制台编辑器 |
| **测试** | ✅ Jest/Vitest 单元测试 | ⚠️ `terraform test` | ❌ |
| **CI/CD** | ✅ `cdktf synth` + `cdktf deploy` | ✅ `terraform apply` | ⚠️ 需调 RFS API |
| **生态** | Terraform provider 生态 | Terraform provider 生态 | 同 provider |
| **团队匹配** | ✅ 用户有 AWS CDK + TS 经验 | 需学 HCL | — |

## 拒绝的方案

### Terraform HCL

- 声明式 DSL，小型项目写起来简单
- 但有条件逻辑和循环时表达能力受限（`count`、`for_each` 语法晦涩）
- 无编译期类型检查，错误发现晚

### RFS（华为云资源编排服务）

- RFS 本质上是一个托管的 Terraform 引擎，底层用同一个 `huaweicloud` provider
- 不能本地 `plan`，只能控制台操作，开发体验差
- `.tf` 文件可在 Terraform CLI 和 RFS 之间无缝迁移，先本地用 Terraform CLI 开发，控制台上传同一份文件即可

### AWS CDK 式原生 CDK

- 华为云没有自研 CDK，CDKTF 是最接近的方案

## 影响

### AgentArts 层

- 所有 AgentArts 配置集中在 `.agentarts_config.yaml`
- 部署命令：`agentarts launch`
- 不需要 Terraform 或 CDKTF

### 华为云基础资源层（触发条件）

建立 `infra/` 目录的时机：第一次需要 `agentarts_config.yaml` 管不到的资源时。

```
infra/
├── main.ts              # CDKTF 入口
├── stacks/
│   └── pa-stack.ts      # PersonalAssistantStack
├── package.json          # cdktf + @cdktf-provider-huaweicloud
└── tsconfig.json
```

典型 CDKTF 代码：

```typescript
import { Construct } from "constructs";
import { App, TerraformStack } from "cdktf";
import { ObsBucket } from "@cdktf-provider-huaweicloud/obs";

class PersonalAssistantStack extends TerraformStack {
  constructor(scope: Construct, id: string) {
    super(scope, id);

    new ObsBucket(this, "web-chat", {
      bucket: "personal-assistant-web-chat",
      acl: "public-read",
    });
  }
}

const app = new App();
new PersonalAssistantStack(app, "pa");
app.synth();
```

部署流程：

```bash
cd infra
npm install
npx cdktf synth       # 生成 Terraform JSON
npx cdktf deploy       # 执行部署
```

### 与 agentarts 的关系

两者互不冲突，管不同层的资源：

```
.agentarts_config.yaml    → AgentArts 层（容器/认证/可观测）
infra/**/*.ts             → 华为云基础资源层（OBS/RDS/IAM）
```

## 参考

- [CDK for Terraform 文档](https://developer.hashicorp.com/terraform/cdktf)
- [HuaweiCloud Terraform Provider](https://registry.terraform.io/providers/huaweicloud/huaweicloud)
- `architecture/devops/cicd.md` #4 IaC 详细说明
