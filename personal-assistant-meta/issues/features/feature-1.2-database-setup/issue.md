---
status: backlog
---

# Feature 1.2: PostgreSQL 数据库集成

为 Personal Assistant 建立持久化数据库基础设施。本 Feature 独立于 Feature 1-9 之外，是 Feature 4（Inbound Identity）和 Feature 6-8（Tools）的前置依赖。

---

## 背景

AgentArts Memory Service 覆盖了对话历史和用户偏好的存储，但以下数据需要项目自行持久化：

- 用户-渠道 ID 映射（飞书 user_id ↔ Entra ID sub ↔ Web Chat session）
- OAuth refresh token
- M2M API Key / STS 配置等工具凭据
- AgentArts Memory 不覆盖的结构化用户偏好

数据库选型已在 ADR-012 确定为 PostgreSQL 16。

## 范围

- Docker Compose 配置（本地开发：`postgres:16-alpine`）
- `app/database.py` — SQLAlchemy 2.0 async engine + session factory
- 初始表结构（Migration）：
  - `user_channel_mapping` — 用户-渠道 ID 映射
  - `oauth_tokens` — OAuth refresh token
  - `tool_configs` — 工具配置（JSONB）
- `pyproject.toml` 依赖更新：`sqlalchemy[asyncio]`、`asyncpg`
- 本地验证：建表 + CRUD 可用

## 不涉及

- 生产 RDS 部署（Feature 9 一起做，IaC 代码写但 `cdktf deploy` 延后）
- 具体业务逻辑（Feature 4 用 `user_channel_mapping`，Feature 6-8 用 `tool_configs`）
- 数据迁移 / Alembic（初始建表用 raw SQL 或 SQLAlchemy `MetaData.create_all`，规模大了再加 Alembic）

## 任务拆解

### DB-1 Docker Compose

- [ ] `docker-compose.yml`（项目根目录）
  - `postgres:16-alpine`，端口 5432
  - 环境变量 `POSTGRES_USER=pa`、`POSTGRES_PASSWORD=pa_dev`、`POSTGRES_DB=personal_assistant`
  - 持久化 volume `pgdata`

### DB-2 数据库连接模块

- [ ] `app/database.py`
  - `DATABASE_URL` 从环境变量读取（默认 `postgresql+asyncpg://pa:pa_dev@localhost:5432/personal_assistant`）
  - `create_async_engine()` + `async_sessionmaker()`
  - `get_db()` 异步生成器（FastAPI Depends 用）

### DB-3 初始表结构

- [ ] `app/models.py`（或 `app/db/models.py`）
  - `UserChannelMapping` — SQLAlchemy ORM model
  - `OAuthToken` — SQLAlchemy ORM model
  - `ToolConfig` — SQLAlchemy ORM model
- [ ] 建表脚本或 `Base.metadata.create_all` 在 startup 时执行

### DB-4 依赖更新

- [ ] `pyproject.toml` 新增依赖：
  - `sqlalchemy[asyncio]>=2.0`
  - `asyncpg>=0.30`

### DB-5 验证

- [ ] `docker compose up -d db` → PostgreSQL 启动
- [ ] `python -c "from app.database import engine; ..."` → 连接成功
- [ ] 建表 → `\dt` 看到三张表
- [ ] 手动插入/查询一条 `user_channel_mapping` 记录

## 依赖

- Feature 1（Agent 骨架）— 需要项目结构和 `app/` 目录存在

## 被依赖

- Feature 4（Inbound Identity）— 需要 `user_channel_mapping` + `oauth_tokens`
- Feature 6-8（Tools）— 需要 `tool_configs`

## 参考

- `ADR-012` — 持久化数据库选型（PostgreSQL 16）
- `ADR-006` — IaC 工具选型（生产 RDS 部署走 CDKTF）
- `ADR-004` — FastAPI 替代 AgentArtsRuntimeApp
- `architecture/devops/cicd.md` #4 — RDS PostgreSQL 触发条件
- `issues/features/feature-4-inbound-identity/issue.md` — 核心消费方
