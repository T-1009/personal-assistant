# Features

Personal Assistant 开发计划，11 个 Feature（含 1 个基础设施前置 Feature + 10 个 Phase Feature）。

渠道策略：Web Chat → 飞书 → OfficeClaw。用浏览器快速验证 Agent 核心能力，再接入企业内部 IM 和微信。

## 概览

| Feature | 内容 | 核心交付 | 依赖 | 状态 |
|---------|------|----------|------|------|
| [1](feature-1-agent-skeleton.md) | Agent 骨架 + Web Chat | 浏览器完成流式对话（单 HTML） | 无 | backlog |
| [1.1](feature-1.1-web-chat-frontend/issue.md) | Web Chat 前端工程化 | Vite + React + TypeScript + Tailwind（替换单 HTML） | Feature 1 | backlog |
| [1.2](feature-1.2-database-setup/issue.md) | PostgreSQL 数据库集成 | 持久化基础设施（Docker Compose + SQLAlchemy + 表结构） | Feature 1 | backlog |
| [2](feature-2-memory.md) | Memory 集成 | 跨 Session 记忆（Web Chat 验证） | Feature 1 | backlog |
| [3](feature-3-officeclaw.md) | OfficeClaw 渠道 | 飞书/微信多渠道覆盖（零代码） | Feature 1, 2 | backlog |
| [4](feature-4-inbound-identity.md) | Inbound Identity (OAuth) | Microsoft Entra ID OAuth + JWT + API Key | Feature 1, 2, 1.2 | backlog |
| [5](feature-5-feishu-channel.md) | 飞书渠道 | 飞书 @Bot 完成对话 | Feature 1 | backlog |
| [6](feature-6-github-tool.md) | GitHub Tool (User Federation) | Agent 代用户查 GitHub Issues | Feature 1, 2, 4 | backlog |
| [7](feature-7-m2m-tool.md) | 内部 API Tool (M2M) | Agent 调企业内部 API | Feature 1, 4 | backlog |
| [8](feature-8-sts-tool.md) | 云资源 Tool (STS) | Agent 访问 OBS 等云资源 | Feature 1, 4 | backlog |
| [9](feature-9-deployment.md) | 部署上线 + 可观测 | 生产环境 + 三渠道验证 | Feature 1-8, 1.1 | backlog |

## 依赖关系

```mermaid
flowchart TD
    F1["Feature 1: Agent + Web Chat"] --> F1_1["Feature 1.1: 前端工程化"]
    F1 --> F1_2["Feature 1.2: PostgreSQL"]
    F1_2 --> F4["Feature 4: Inbound Identity"]
    F1 --> F2["Feature 2: Memory"]
    F1 --> F3["Feature 3: OfficeClaw"]
    F2 --> F3
    F1 --> F4
    F2 --> F4
    F1 --> F5["Feature 5: 飞书"]
    F1 --> F6["Feature 6: GitHub Tool"]
    F2 --> F6
    F4 --> F6
    F4 --> F7["Feature 7: M2M Tool"]
    F4 --> F8["Feature 8: STS Tool"]
    F3 --> F9["Feature 9: 部署上线"]
    F5 --> F9
    F6 --> F9
    F7 --> F9
    F8 --> F9
```

## 渠道上线顺序

```
Feature 1: Web Chat  ← 第一条渠道，浏览器直接验证 Agent
Feature 5: 飞书      ← 第二条渠道，企业内部 IM 接入
Feature 3: OfficeClaw ← 最后，零代码加微信覆盖
```

## 相关文档

| 文档 | 路径 |
|------|------|
| 总体功能规格 | `../specs/overall_specifications.md` |
| 架构设计 | `../architecture/overall_architecture.md` |
| ADR | `../architecture/ADR/README.md` |
| DevOps | `../architecture/devops/` |
| 领域词典 | `../specs/dictionary.md` |
