# Personal Assistant Infra

OpenTofu + HCL 的华为云基础资源空基线。Production Web Chat 由 Cloudflare
Pages 托管，前端请求通过 Pages Function same-origin Proxy 转发到 AgentArts
Gateway；本目录不管理 Cloudflare resources。

Legacy `personal-assistant-web-chat` OBS static website 和
`chat.resource-governance.cloud` CNAME 已退役。注册域名对应的
`resource-governance.cloud` DNS Zone 保留在华为云，不再由 OpenTofu 管理。

## 保留策略

- 保留 `personal-assistant-infra/`，用于未来 RDS、IAM、VPC、EIP 等资源。
- 保留 `pa-terraform-state` OBS backend，供未来 HuaweiCloud IaC 继续使用。
- Pull Request 和 `main` push 只执行 `tofu plan`。
- `tofu apply` 只能通过手动 `workflow_dispatch` 并显式选择 `apply` 执行。

## 前置条件

- OpenTofu CLI ≥ 1.9
- Provider credentials：`HW_ACCESS_KEY` / `HW_SECRET_KEY`
- OBS backend credentials：`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- 与待管理资源匹配的最小 IAM permissions

## 本地验证

```bash
cd personal-assistant-infra

export HW_ACCESS_KEY="<your-access-key>"
export HW_SECRET_KEY="<your-secret-key>"
export AWS_ACCESS_KEY_ID="$HW_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$HW_SECRET_KEY"

tofu init
tofu fmt -check -recursive
tofu validate
tofu plan
```

不得对未 review 的 plan 执行 `tofu apply` 或 `tofu destroy`。

## 目录结构

```text
personal-assistant-infra/
├── main.tf                # OpenTofu、Provider 与 OBS backend
├── variables.tf           # 通用变量
├── .terraform.lock.hcl    # Provider 版本锁
├── .gitignore
├── AGENTS.md              # IaC 开发规范
└── README.md              # 本文件
```

新增资源时按类型创建独立文件，例如 `rds.tf`、`iam.tf`、`vpc.tf`。

## Legacy retirement 记录

2026-06-19：Production Web Chat 已由 Cloudflare Pages 承载。审计确认 DNS
Zone 仅包含 SOA、NS 和待删除的 `chat` CNAME；OBS bucket 启用 versioning，
包含 508 个 object versions 和 74 个 delete markers。退役过程中保留 DNS
Zone 与 `pa-terraform-state`，删除 CNAME 和 Legacy website bucket。

## 相关文档

- [ADR-006 IaC 选型](../personal-assistant-meta/architecture/ADR/ADR-006-iac-cdktf-typescript.md)
- [Cloudflare Pages](../personal-assistant-meta/architecture/cloud-service/cloudflare/pages.md)
- [CI/CD 架构](../personal-assistant-meta/architecture/devops/cicd.md)
- [Legacy domain 记录](../personal-assistant-meta/architecture/cloud-service/domain.md)
