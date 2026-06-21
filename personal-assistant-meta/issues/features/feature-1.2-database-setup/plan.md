# Feature 1.2 Implementation Plan: RDS PostgreSQL 17

> 日期：2026-06-21 | 状态：In Progress

## 目标

在 `cn-southwest-2` 创建按需计费的 RDS for PostgreSQL 17，并通过 VPC 私网
连接 AgentArts Runtime。生产 Checkpointer 从进程内 `InMemorySaver` 切换为
shared durable `AsyncPostgresSaver`。

```mermaid
flowchart LR
    Gateway["AgentArts Gateway"] --> Runtime["AgentArts Runtime<br/>VPC Mode"]
    Runtime -->|"TCP 5432"| RDS["RDS PostgreSQL 17<br/>Single / 1C2G / 40 GB"]
    RDS --> CP["LangGraph Checkpoint Tables"]
```

## 已确认资源

| 项目 | 值 |
|------|----|
| Region | `cn-southwest-2` |
| VPC | `vpc-default-smb` (`172.31.0.0/16`) |
| Subnet | `subnet-default-smb` (`172.31.0.0/20`) |
| Availability Zone | `cn-southwest-2f`（控制台可用区4） |
| Flavor | `rds.pg.n1.medium.2`（通用型 1 vCPU / 2 GB） |
| Engine | PostgreSQL 17 |

## Infra

1. OpenTofu 使用 Data Source 引用现有 VPC/Subnet，不接管其 lifecycle。
2. 创建 `pa-runtime-sg` 与 `pa-rds-sg`。
3. `pa-rds-sg` 允许任何可路由 IPv4 来源访问 TCP 5432，避免 AgentArts 托管
   网络的实际源地址影响业务连通性。RDS 不绑定 EIP，因此仍无公网访问路径。
4. 创建按需、Single、SSD 云盘 40 GB 的 `pa-postgresql`。
5. 不绑定 EIP，不开启磁盘加密，不开启自动扩容。
6. 自动备份保留 7 天。
7. 创建 `personal_assistant` Database 和 `pa_app` Application Role。
8. Password 仅通过敏感 OpenTofu Variable 注入，不进入 Git 或 Output。

## Service

1. 新增 `langgraph-checkpoint-postgres` 依赖。
2. `POSTGRES_DSN` 使用 `pa_app` 和 RDS Private IP。
3. 使用 `AsyncPostgresSaver`，在 FastAPI startup 执行 `setup()`。
4. shutdown 时关闭 Checkpointer Connection Pool。
5. Runtime 切换为 VPC Mode，使用目标 VPC/Subnet 和 `pa-runtime-sg`。

## 验证

- `tofu fmt -check -recursive`
- `tofu validate`
- Review `tofu plan`
- `tofu apply`
- RDS 状态为 `ACTIVE`
- Runtime 内成功执行 Checkpointer `setup()`
- 两次相同 `thread_id` 的 Invocation 能恢复上下文
- `uv run ruff check .`
- `uv run pytest tests/`
- E2E `/ping` 与 `/invocations`

## 风险与回退

| 风险 | 缓解 |
|------|------|
| VPC Mode 影响公网 Egress | 部署后验证 DeepSeek/Microsoft Graph；必要时增加 NAT Gateway + SNAT |
| 1C2G 连接数或内存不足 | 监控 CPU、Memory、Connections 后在线扩规格 |
| 40 GB 无自动扩容 | 设置容量告警并维护人工扩容 Runbook |
| Password 已出现在会话记录 | 首次连通后立即轮换为随机 Secret |
| Single Instance 无 HA | 当前成本优先；生产 SLA 提升时迁移为 Primary/Standby |
