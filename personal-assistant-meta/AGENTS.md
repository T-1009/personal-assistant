# AGENTS.md

> 本文件是 **personal-assistant-meta** 目录的专用 instructions，仅适用于该目录下的相关工作。

## Diagram Policy

- **所有 diagram 必须使用 [Mermaid](https://mermaid.js.org/) 格式**，包括但不限于 Flowchart、Sequence Diagram、Class Diagram、State Diagram、ER Diagram、Gantt Chart、Pie Chart 等。
- 禁止使用 ASCII art 或其他非 Mermaid 格式绘制图表。

## Language Policy

- **Primary language for documentation**: Chinese（中文）
- **Secondary language**: English（英文）
- **Software engineering terminology**: Always use the original English term. Do NOT translate technical terms into Chinese.

### 专业术语对照示例

以下是本项目文档中必须使用英文原文的术语，以及常见的错误翻译对照：

| English (use this)          | Chinese (DO NOT use)      |
| --------------------------- | ------------------------- |
| Agent                       | 智能体（正文可使用）        |
| Runtime                     | 运行时                     |
| Sandbox                     | 沙箱                       |
| Memory                      | 记忆库                     |
| Gateway                     | 网关                       |
| SDK                         | -                          |
| MCP (Model Context Protocol) | -                         |
| API                         | -                          |
| CLI                         | -                          |
| IAM                         | -                          |
| QPS                         | -                          |
| Dockerfile                  | -                          |
| CI/CD                       | -                          |
| PR (Pull Request)           | -                          |
| commit                      | -                          |
| branch                      | -                          |
| deploy / deployment         | -                          |
| rollback                    | -                          |
| scaling                     | -                          |
| container                   | -                          |
| image                       | -                          |
| token                       | -                          |
| prompt                      | -                          |
| RAG                         | -                          |
| LLM                         | -                          |

**原则**：当一个术语在软件工程领域有广泛接受的英文表达时，优先使用英文原文，避免生硬的直译造成歧义。

### 正文写作规范

- 正文以中文撰写，保持自然流畅。
- 英文术语首次出现时可附中文说明，后续直接使用英文原文。
- 代码块、配置文件、命令行示例保持英文。
- 代码注释推荐英文，但面向中文读者的说明性注释可使用中文。
- README.md、CHANGELOG.md 等对外文档以中文为主，英文摘要可附在关键段落后方。
