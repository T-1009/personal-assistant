---
status: done
---

# Refactor 11: 加固 `/invocations` API contract

## Motivation

`POST /invocations` 同时支持 sync JSON 与 SSE streaming，但此前存在几处 contract
不一致：

- `stream` 使用 Python truthiness 判断，字符串 `"false"` 会错误进入 streaming
- sync 与 streaming 对纯空白 `message` 的校验结果不同
- OpenAPI 未完整描述 JSON/SSE 双响应和错误响应
- 服务端未校验 `Accept`，也无法从日志区分 sync/stream 流量

## Changes

- 使用 Pydantic model 定义 request、JSON response 和 error response
- `stream` 仅接受 JSON boolean，同时保持既有 HTTP 400 错误语义
- sync 与 streaming 统一拒绝空白 `message`
- 缺省或通配 `Accept` 保持兼容；明确排除目标 media type 时返回 406
- invocation 日志增加 `mode=sync|stream`
- OpenAPI 自动生成 JSON 与 `text/event-stream` 两种 200 response media type

## Expected Result

- API contract、runtime validation 与 OpenAPI 保持一致
- Web Chat 和现有通配 `Accept` 客户端行为不变
- sync/stream 流量可在日志中独立统计

## Four-Question Gate

| Question | Answer |
|---|---|
| Is it best practice? | Yes |
| Is it industry standard? | Yes |
| Is it conventional? | Yes |
| Is it modern? | Yes |

## Affected Architecture Docs

无架构变更；本次仅加固现有 `POST /invocations` contract。
