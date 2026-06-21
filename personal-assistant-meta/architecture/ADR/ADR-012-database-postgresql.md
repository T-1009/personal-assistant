# ADR-012: 持久化数据库选型

> 状态：Accepted（2026-06-21 修订） | 日期：2026-06-07

---

## 背景

Personal Assistant 的核心存储——对话历史和用户偏好——由 AgentArts Memory Service 托管（ADR-003），不需要自建数据库。但随着 Feature 4（Inbound Identity）引入多渠道接入，以下数据需要项目自行持久化：

| 数据 | 来源 | 读写模式 |
|------|------|----------|
| 用户-渠道 ID 映射 | 飞书 user_id ↔ Entra ID sub ↔ Web Chat session | 写少读频繁（每次请求） |
| OAuth refresh token | Microsoft Entra ID token 交换 | 写少读中等 |
| 工具配置（M2M API Key 等） | Feature 6-8 | 写极少读频繁（每次工具调用） |
| AgentArts Memory 不覆盖的用户偏好 | Feature 2+ | 写少读频繁 |

这些数据都是**结构化的关系型数据**（一对一映射、外键关联），不是文档型或纯 KV。

## 决策

**使用 PostgreSQL 17，本地开发用 Docker Compose，生产走华为云 RDS for
PostgreSQL。**

2026-06-21 修订：目标 Region `cn-southwest-2` 已通过 HuaweiCloud Provider
实时查询确认 PostgreSQL 17 可售，PostgreSQL 18 返回 `Invalid database version`。
因此将原 PostgreSQL 16 基线升级为当前区域最新可用的 PostgreSQL 17。

选择依据：

| 因素 | PostgreSQL 17 | SQLite | MySQL 8.0 | GaussDB | Redis | MongoDB |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| **关系型数据建模** | ✅ 最强（CTE、窗口函数、JSONB） | ✅ 基础 SQL | ⚠️ 弱于 PG（无 DISTINCT ON、LATERAL 有限） | ✅ PG 兼容 | ❌ 非关系型 | ❌ 文档型不适配 |
| **并发 / 连接池** | ✅ 原生连接池，生产级 | ❌ 单写者，多容器并发锁竞争 | ✅ 连接池 | ✅ 同 PG | ✅ 但用错工具 | ✅ 但用错工具 |
| **Python 生态** | ✅ SQLAlchemy 2.0 + asyncpg（首选） | ✅ SQLAlchemy + aiosqlite | ✅ SQLAlchemy + asyncmy | ⚠️ psycopg2 兼容 | ✅ redis-py | ⚠️ motor/beanie |
| **华为云托管** | ✅ RDS PostgreSQL（cicd.md 已预留） | ❌ 不托管 SQLite | ✅ RDS MySQL | ✅ 自研但锁定华为 | ❌ DCS Redis | ❌ DDS MongoDB |
| **云中立** | ✅ 标准 PG，可迁任何云 | N/A（本地文件） | ✅ 可迁 | ❌ 锁定华为云 | ✅ | ✅ |
| **团队匹配** | 无偏好，但 PG 是 FastAPI 生态默认 | — | 无偏好 | — | — | — |

## 拒绝的方案

### SQLite

本地单进程开发完全可行（见下方「本地开发策略」），但**不能作为唯一选择**：

- 多容器（AgentArts Runtime 可能起多实例）并发写会锁竞争，WAL 模式下也只有一个写者
- 华为云不托管 SQLite，生产无法直接迁移
- 但它作为本地开发的零依赖方案有价值——见「本地开发策略」

### MySQL 8.0

MySQL 在 8.0 后大幅改进（CTE、窗口函数、JSON），但 PostgreSQL 在以下方面仍领先：

- `DISTINCT ON` / `RETURNING` / `LATERAL` 语法更丰富，复杂查询表达力更强
- JSONB 索引（GIN）比 MySQL JSON 更成熟
- 本项目的 agent 配置和工具配置天然适合 JSONB 列
- 既然两边都没有遗留负担，选更强的

### GaussDB

华为自研的 PG 兼容数据库。语法兼容性好，但：

- **锁定华为云**——未来如果迁到 AWS/Azure/GCP 或自建机房，GaussDB 无法带走
- 对简历展示价值不如标准 PG（面试官问"你用什么数据库"，回答"标准 PostgreSQL"比"华为自研 GaussDB"更通用）
- 学习资源、社区问题排查远不如 PG 丰富

### Redis 作为 Primary Store

Redis 的正确角色是 Cache / Session Store，不是 primary database：

- RDB/AOF 持久化无法保证 crash 后数据不丢
- 用户-渠道映射丢了 = 用户身份断裂，不可接受
- 不适合复杂查询（"列出某用户的所有渠道绑定"）

### MongoDB

项目数据是关系型的（用户 ↔ 渠道 ↔ token → 工具配置），天然适合关系模型：

- `user_channel_mapping` 表：内部 user_id + channel type + external id，三个字段一个唯一约束
- `oauth_tokens` 表：user_id FK → user_channel_mapping，标准关系
- MongoDB 的文档嵌套在这里不带来收益，反而让跨集合查询变复杂

## 影响

### 本地开发策略

使用 Docker Compose 起 PostgreSQL 17，Zero-config 可选方案：

```yaml
# docker-compose.yml（项目根目录）
services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: pa
      POSTGRES_PASSWORD: pa_dev
      POSTGRES_DB: personal_assistant
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

> **过渡期策略**：Feature 1-3 阶段如果不愿意跑 Docker，SQLAlchemy 可以用 `sqlite+aiosqlite:///dev.db` 一行改 URL 切 SQLite，Feature 4 再切回 PostgreSQL。同一个 ORM，Schema 不变。

### 连接方式

```python
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://pa:pa_dev@localhost:5432/personal_assistant")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

### 初始 Schema

Feature 4 上线时需要建以下表：

```sql
-- 用户-渠道 ID 映射
CREATE TABLE user_channel_mapping (
    id              BIGSERIAL PRIMARY KEY,
    internal_user_id TEXT NOT NULL,
    channel         TEXT NOT NULL CHECK (channel IN ('entra_id', 'feishu', 'officeclaw', 'web_chat')),
    channel_user_id TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (internal_user_id, channel),
    UNIQUE (channel, channel_user_id)
);

-- OAuth Token
CREATE TABLE oauth_tokens (
    id              BIGSERIAL PRIMARY KEY,
    mapping_id      BIGINT NOT NULL REFERENCES user_channel_mapping(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL CHECK (provider IN ('microsoft_entra_id')),
    access_token    TEXT,
    refresh_token   TEXT,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 工具配置（Feature 6-8）
CREATE TABLE tool_configs (
    id              BIGSERIAL PRIMARY KEY,
    tool_name       TEXT NOT NULL UNIQUE,
    config          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX idx_user_channel_internal ON user_channel_mapping(internal_user_id);
CREATE INDEX idx_oauth_tokens_mapping ON oauth_tokens(mapping_id);
```

### Feature 触发点

| Feature | 需要数据库 | 建表 |
|---------|:---:|------|
| Feature 1-3 | ❌ 不需要 | 无 |
| Feature 4（Inbound Identity） | ✅ | `user_channel_mapping` + `oauth_tokens` |
| Feature 6-8（Tools） | ✅ | `tool_configs` |

### 生产 RDS Baseline

生产基础资源由 OpenTofu + HCL 管理（ADR-006）。初始部署采用低成本、可升级的
Baseline：

| 配置项 | Baseline | 说明 |
|--------|----------|------|
| Region | `cn-southwest-2` | 与 AgentArts Runtime 同 Region |
| 计费 | `postPaid`（按需） | 适合早期负载，避免预付费锁定 |
| Engine | PostgreSQL 17 | 2026-06-21 实测的区域最新可用 Major Version |
| Instance Mode | Single | 初期成本优先；达到生产可用性要求后升级 HA |
| Flavor | 通用型 1 vCPU / 2 GB | 当前流量起步规格，以上线监控数据决定扩容 |
| Storage | SSD 云盘 40 GB | 开启使用率告警；建议启用自动扩容或预设扩容 Runbook |
| Availability Zone | 可用区 4 | 与目标 Subnet 和 Flavor 库存保持一致 |
| Parameter Template | `Default-PostgreSQL-17` | 初期不做未经基准测试的参数调优 |
| Timezone | `UTC+08:00` | 业务时间；数据字段仍统一使用 `TIMESTAMPTZ` |
| Backup | 每日自动备份，保留 7 天 | 上线前必须完成一次恢复演练 |
| Disk Encryption | KMS 加密 | 数据包含身份映射和 credential material，创建时启用 |
| Public EIP | 不绑定 | RDS 仅允许私网访问 |

```mermaid
flowchart LR
    Gateway["AgentArts Gateway"] --> Runtime["AgentArts Runtime<br/>VPC Mode"]
    Runtime -->|"Private network :5432"| RDS["RDS PostgreSQL 17<br/>No EIP"]
    Runtime --> NAT["NAT Gateway + EIP<br/>only if outbound Internet is required"]
    NAT --> External["DeepSeek / Microsoft Graph"]
```

网络与权限约束：

- Runtime 与 RDS 位于同一 VPC，或位于已经建立受控路由的 VPC；
- 不使用 `default` Security Group。为 Runtime 和 RDS 分别创建
  `pa-runtime-sg`、`pa-rds-sg`；
- `pa-rds-sg` 允许任何可路由 IPv4 来源的 TCP 5432 Ingress，避免 AgentArts
  托管网络源地址影响业务连通性；RDS 不绑定 EIP，因此仍无公网访问路径；
- RDS 不绑定 EIP；若 Runtime 的 VPC Mode 无默认公网 Egress，使用 NAT Gateway
  + SNAT + EIP，仅提供主动出站；
- `root` 仅用于实例初始化和管理。应用连接使用独立的 least-privilege Role，
  例如 `pa_app`，不得使用 `root`；
- RDS 管理密码不得写入 HCL、tfvars、Git 或 Output，必须通过受保护的 Secret
  注入；
- OpenTofu Cloud Resource Name 遵循 `pa-` 前缀，实例名使用
  `pa-postgresql`。

核心 OpenTofu 形态：

```hcl
resource "huaweicloud_rds_instance" "postgresql" {
  name              = "pa-postgresql"
  charging_mode     = "postPaid"
  flavor            = var.rds_flavor
  vpc_id            = huaweicloud_vpc.main.id
  subnet_id         = huaweicloud_vpc_subnet.rds.id
  security_group_id = huaweicloud_networking_secgroup.rds.id
  availability_zone = [var.rds_availability_zone]

  db {
    type     = "PostgreSQL"
    version  = "17"
    password = var.rds_admin_password
  }

  volume {
    type               = "CLOUDSSD"
    size               = 40
    disk_encryption_id = var.rds_kms_key_id
  }

  backup_strategy {
    start_time = "18:00-19:00"
    keep_days  = 7
  }
}
```

## 参考

- `ADR-003` — AgentArts 平台作为基础设施（Memory Service 托管对话存储）
- `ADR-006` — IaC 工具选型（OpenTofu + HCL）
- `architecture/devops/cicd.md` #4 — RDS PostgreSQL 触发条件
- `issues/features/feature-4-inbound-identity/issue.md` — Inbound Identity Feature Spec
