# personal-assistant-service

> 本文件是 **personal-assistant-service** 目录的专用 instructions，仅适用于该目录下的相关工作。

## Directory Guide

`personal-assistant-service/` 是系统的**后端服务**，运行在 AgentArts Runtime 上的 AI Agent 服务，处理对话逻辑、日程/邮件/笔记/任务管理、跨 Session Memory、用户委托等核心能力。

## Project Overview

**personal-assistant-service** 是运行在 AgentArts Runtime 上的 AI Agent 服务系统，通过 FastAPI 提供对话接口，处理日程、邮件、笔记和任务管理，并实现跨 Session Memory 与用户委托功能。

## Tech Stack

- **核心语言与框架**: Python 3.12+, FastAPI, Uvicorn
- **AI 与 Agent 框架**: DeepAgents, LangChain (langchain-core, langchain-openai), LangGraph (`langgraph-checkpoint-sqlite` 用于状态持久化)
- **云服务与部署**: AgentArts SDK (`agentarts-sdk`), Huawei Cloud SDK (`huaweicloudsdkiam`)
- **开发工具链**: `uv` (包管理), `Ruff` (代码检查与格式化), `pytest` (测试), `Chainlit` (本地调试/界面)

## Build and Test Commands

- **依赖安装**: `uv sync`
- **本地启动**: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload`
- **代码检查与格式化**: `uv run ruff check .` 以及 `uv run ruff format .`
- **运行测试**: `uv run pytest tests/`

## Code Style Guidelines

- 遵循 **PEP8** 代码规范。
- 强制使用 **Ruff** 进行代码 Lint（开启如 E, F, I, N, UP, B, C4, SIM 规则）和代码格式化（双引号，空格缩进）。
- FastAPI 路由只负责 HTTP 层请求与响应转换，AgentCore 和业务逻辑尽量与之解耦。

## Testing Instructions

- 单元测试和集成测试统一放置在 `tests/` 目录。
- 采用 **pytest** 作为测试框架，支持 `pytest-asyncio` 测试异步方法。
- 编写测试时，需 mock 外部依赖，尤其是外部云服务 API 或大模型接口调用。
- 提交代码前，必须确保所有的本地 pytest 均执行通过。
