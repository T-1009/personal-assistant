# personal-assistant-client

> 本文件是 **personal-assistant-client** 目录的专用 instructions，仅适用于该目录下的相关工作。

## Directory Guide

`personal-assistant-client/` 是系统的**前端应用**，提供 Web Chat 对话界面，负责用户交互、消息渲染，以及飞书、OfficeClaw 等多接入渠道的客户端适配层。

开始前先阅读项目根目录的 [`AGENTS.md`](../AGENTS.md) 了解整体项目结构和规范。

## Project Overview

**personal-assistant-client** 是提供给用户的对话界面前端应用。基于 Vite + React 19 + TypeScript 构建。采用 Tailwind CSS v4 实现响应式且符合 Apple 风格设计规范的 UI。它不仅提供 Web 端对话交互，还包含了适配飞书、OfficeClaw 等渠道的逻辑层。

## Tech Stack

- **核心框架**: React 19, TypeScript 5.8
- **构建工具**: Vite 6
- **UI 与样式**: Tailwind CSS v4, shadcn/ui, Radix UI 组件, Lucide React (图标)
- **对话/Agent 组件层**: `@assistant-ui/react` 及其 Markdown 渲染插件
- **状态管理**: Zustand
- **测试工具**: Vitest, React Testing Library

## Build and Test Commands

- **依赖安装**: `npm install`
- **本地启动**: `npm run dev`
- **构建生产产物**: `npm run build` (内部包含 `tsc -b && vite build`)
- **运行测试**: `npm run test` (基于 vitest)

## Code Style Guidelines

- 遵循 React 官方最佳实践以及 TypeScript 严格类型检查安全规范。
- 样式遵循 `DESIGN.md` 中定义的 Design Tokens。全部使用 Tailwind CSS 进行原子类编写，禁止内联/硬编码 hex 颜色和绝对像素值。
- 保持客户端逻辑轻量化，复杂业务逻辑和计算应尽量下放给后端 Service 层处理。

## Testing Instructions

- 采用 **Vitest** 作为测试框架，结合 `@testing-library/react` 进行组件渲染与交互测试。
- 提交前请运行 `npm run test` 确保已有测试用例全部通过，没有发生破坏性变更。

## 设计指引

前端 UI 设计遵循 Apple 风格设计语言，详见 [`DESIGN.md`](DESIGN.md)。所有颜色、字体、间距、圆角、阴影和组件样式均按照 DESIGN.md 中定义的 design token 规范，禁止内联 hex 色值或硬编码尺寸。
