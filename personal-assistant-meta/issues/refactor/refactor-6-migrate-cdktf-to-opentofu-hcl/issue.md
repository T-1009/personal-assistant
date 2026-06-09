---
status: backlog
---

# Refactor 6: 从 CDKTF 迁移到 OpenTofu + HCL

将 `personal-assistant-infra/` 的 IaC 方案从已废弃的 CDK for Terraform (CDKTF) 迁移到 OpenTofu + HCL——放弃 CDK-for-Terraform 整个技术路线，回归 IaC 行业标准。

HashiCorp (IBM) 于 2025 年 12 月 10 日正式归档 CDKTF 仓库。评估了社区 fork CDK Terrain (cdktn) 后，决定不延续 CDK-for-Terraform 路线，而是直接迁移到 Linux 基金会托管的 OpenTofu + 原生 HCL。详见 [ADR-006 修订](../../architecture/ADR/ADR-006-iac-cdktf-typescript.md)。

---

## 背景

### CDKTF 废弃与 CDK Terrain 评估

| 选项 | 评估结果 |
|------|----------|
| **继续用 CDKTF** | ❌ 已归档，无安全补丁 |
| **迁移到 CDK Terrain (cdktn)** | ⚠️ 社区 fork < 6 个月，ThoughtWorks Radar "Assess"，长期存活风险高；CDK-for-Terraform 方向本身已被市场否定 |
| **迁移到 OpenTofu + HCL** | ✅ Linux 基金会托管、100% Terraform 兼容、无中间编译层、生态资料最丰富 |

### 为什么放弃 CDK-for-Terraform 路线

1. **中间层负担**：TypeScript → JSON → HCL → Terraform/tofu apply，报错信息需要反向映射，排错成本高
2. **当前 infra 规模极小**：1 个 Stack，1 个 OBS Bucket 资源，~35 行 TypeScript。CDKTF 的类型安全和抽象能力没有实际收益
3. **HCL 学习成本低**：1-2 天可上手，且 99% Terraform 教程/代码库直接复用
4. **团队匹配**：用户有 AWS CDK 经验，但 HCL 是 IaC 行业的通用语言——任何做 DevOps 的人都能读懂 `.tf` 文件

---

## 范围

### 必须完成

- [ ] **替换 IaC 代码**：删除所有 TypeScript/CDKTF 文件，用 HCL 重写
- [ ] **安装 OpenTofu CLI**：`brew install opentofu`
- [ ] **迁移 Terraform state**（如果已部署过）：确保 `tofu plan` 显示零变更
- [ ] **更新 infra AGENTS.md**：技术栈、目录结构、命令全部重写
- [ ] **修订 ADR-006**：记录 CDKTF → OpenTofu + HCL 的决策变更
- [ ] **更新 cicd.md §4**：Layer 3 IaC 工具从 Terraform CLI 修正为 OpenTofu + HCL，移除 CDKTF 内容

### 不涉及

- CI/CD 流水线变更（GitHub Actions 中等价替换 `tofu plan/apply`）
- 华为云凭据管理变更（AK/SK 通过环境变量注入，方式不变）
- Provider 版本升级（保持 `huaweicloud/huaweicloud@~> 1.92`）
- RFS（华为云资源编排服务）——继续使用本地 CLI 模式

---

## 影响

### 修改/删除文件

| 文件 | 改动 |
|------|------|
| `personal-assistant-infra/main.tf` | **新增**：provider + backend 配置 |
| `personal-assistant-infra/obs.tf` | **新增**：OBS Bucket 资源定义（等价于当前 `pa-stack.ts`） |
| `personal-assistant-infra/variables.tf` | **新增**：敏感变量声明（AK/SK） |
| `personal-assistant-infra/outputs.tf` | **新增**：Stack outputs |
| `personal-assistant-infra/terraform.tfvars` | **新增**：变量值（gitignored） |
| `personal-assistant-infra/main.ts` | **删除**：CDKTF TypeScript 入口 |
| `personal-assistant-infra/stacks/pa-stack.ts` | **删除**：TypeScript Stack 定义 |
| `personal-assistant-infra/stacks/__tests__/` | **删除**：Jest 测试目录 |
| `personal-assistant-infra/constructs/.gitkeep` | **删除**：不再需要 |
| `personal-assistant-infra/package.json` | **删除**：不再需要 Node.js/npm |
| `personal-assistant-infra/package-lock.json` | **删除** |
| `personal-assistant-infra/tsconfig.json` | **删除** |
| `personal-assistant-infra/jest.config.js` | **删除** |
| `personal-assistant-infra/cdktf.json` | **删除**：CDKTF 配置文件 |
| `personal-assistant-infra/.gen/` | **删除**：自动生成的 provider bindings |
| `personal-assistant-infra/cdktf.out/` | **删除**：CDKTF 输出目录 |
| `personal-assistant-infra/AGENTS.md` | **重写**：技术栈、目录结构、命令全部替换 |
| `personal-assistant-infra/.gitignore` | 更新排除规则（添加 `.terraform/`, `*.tfvars`, `*.tfstate*` 等，移除 cdktf 相关） |
| `personal-assistant-meta/architecture/ADR/ADR-006-iac-cdktf-typescript.md` | **修订**：标题、决策、影响全部更新 |

### 新增的 infra 目录结构

```
personal-assistant-infra/
├── main.tf                # Terraform/Provider 配置 + Backend
├── obs.tf                 # OBS Bucket 资源
├── variables.tf           # 变量声明
├── outputs.tf             # 输出值
├── terraform.tfvars       # 变量赋值（gitignored）
├── .terraform.lock.hcl    # Provider 版本锁（git tracked）
├── .gitignore             # 排除规则
├── AGENTS.md              # 本目录专用 instructions
└── README.md              # 快速开始
```

### 测试影响

- Jest 测试框架随 TypeScript 代码一并移除
- OpenTofu 自身提供 `tofu plan`（dry-run 验证）和 `tofu validate`（语法检查）作为验证手段
- 不引入额外的 IaC 测试框架（如 Terratest），当前资源规模不需要

---

## 任务拆解

### 6.1 安装 OpenTofu 并初始化

- [ ] `brew install opentofu` 安装 OpenTofu CLI
- [ ] 验证：`tofu version`

### 6.2 编写 HCL 文件

- [ ] 编写 `main.tf`：`terraform {}` + `required_providers` + `provider "huaweicloud" {}`
- [ ] 编写 `obs.tf`：`huaweicloud_obs_bucket` 资源，等价于当前 `pa-stack.ts`
- [ ] 编写 `variables.tf`：`ak` / `sk` / `region` 变量，标记 `sensitive = true`
- [ ] 编写 `outputs.tf`：`website_endpoint`
- [ ] 创建 `.gitignore` 更新（`terraform.tfvars`, `.terraform/`, `*.tfstate*`）

### 6.3 验证

- [ ] `tofu init` — 初始化 provider
- [ ] `tofu validate` — 语法验证
- [ ] `tofu fmt -check` — 格式检查
- [ ] `tofu plan` — 对比现有资源（如已部署），确认零变更
- [ ] 与当前 `cdktf synth` 输出（`cdk.tf.json`）对比，资源定义等价

### 6.4 清理旧文件

- [ ] 删除所有 TypeScript/Node.js 相关文件（`main.ts`, `stacks/`, `package.json`, `tsconfig.json`, `jest.config.js`, `cdktf.json`）
- [ ] 删除 `.gen/`, `cdktf.out/`, `node_modules/` 目录
- [ ] 移除 `personal-assistant-infra/` 的 `.gitignore` 中 CDKTF 相关规则

### 6.5 文档更新

- [ ] 重写 `infra AGENTS.md`：OpenTofu + HCL 技术栈
- [ ] 修订 `ADR-006`：记录 CDKTF 废弃 → OpenTofu + HCL 决策
- [ ] 更新 `ADR/README.md`：ADR-006 标题和决策摘要
- [ ] 更新 `cicd.md §4`：移除 CDKTF 内容，Layer 3 明确为 OpenTofu + HCL
- [ ] 更新 `cicd.md §5` 分层总结表

---

## 依赖

- 无外部 issue 依赖（可独立执行）
- OpenTofu 需在本地 macOS 上安装（`brew install opentofu`）
- 如果已通过 CDKTF 部署过 OBS Bucket，需要迁移 state：`tofu import huaweicloud_obs_bucket.web_chat personal-assistant-web-chat`

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 已有 Terraform state 不兼容 | 资源被重建 | `tofu plan` 先验证；如需，通过 `tofu import` 导入已有资源 |
| HCL 语法错误 | 部署失败 | `tofu validate` + `tofu plan` 提前发现 |
| 华为云凭据未配置 | plan/apply 失败 | 同 CDKTF 时期一样通过环境变量注入（`HUAWEICLOUD_SDK_AK/SK`） |
| HCL 学习曲线 | 开发效率短期下降 | 1-2 天，资源量极少（1 个 resource），影响极小 |

---

## 参考

- [OpenTofu 官网](https://opentofu.org)
- [OpenTofu CLI 文档](https://opentofu.org/docs/cli/)
- [HuaweiCloud Provider (OpenTofu Registry)](https://search.opentofu.org/provider/opentofu/huaweicloud)
- [Terraform HCL 语法文档](https://developer.hashicorp.com/terraform/language)
- [CDKTF Sunset Notice (HashiCorp)](https://developer.hashicorp.com/terraform/cdktf)
- [ADR-006: IaC 工具选型](../../architecture/ADR/ADR-006-iac-cdktf-typescript.md)
- [infra AGENTS.md](../../../../personal-assistant-infra/AGENTS.md)
- [cicd.md §4 Layer 3](../../architecture/devops/cicd.md)
- [ThoughtWorks Technology Radar — CDK Terrain](https://www.thoughtworks.com/en-us/radar/tools/cdk-terrain)（Assess — 不推荐采用）
