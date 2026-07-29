# Manual Real-Auth Tests

本目录预留给真实账号、真实 OAuth、真实云环境相关的 E2E 验证。

默认规则：

- 不提交账号、密码、token、OAuth code 或任何 secret。
- 不进入默认 `uv run pytest` / PR gate。
- 测试必须使用 `@pytest.mark.manual`，并通过显式环境变量启用。
- 优先把可自动化且不需要真实账号的覆盖放入 `smoke/`、`browser/` 或 `full_stack/`。

## Feature 14 Gateway G1 Probe

```bash
set PA_E2E_DEPLOYED_BASE_URL=https://agentarts-personal-assistant.pages.dev
set PA_E2E_BEARER_TOKEN=<entra-id-token>
uv run pytest -m manual tests/manual/test_feature_14_gateway_probe.py -vv
```

该 probe 验证 deployed Pages/Gateway 的 Conversation GET/POST/PATCH/DELETE、Runtime Cookie、
同一 HTTPS Cookie 的连续复用、caller Session/User header 无法影响浏览器侧 resolver，以及
archived Invocation 的稳定 409。它不会执行模型，也不暴露 Runtime 内部 routing key。

Gateway 实际收到 resolver Session header、Runtime instance 回收后复用同一 ID、真实 OAuth
complete 和 warm-up p50/p95 仍需要部署侧日志或人工/测量流程，不能由这个黑盒 probe 或
本地 deterministic Agent 代替。

## Feature 18 Report Root Capability

```bash
set PA_E2E_DEPLOYED_BASE_URL=https://agentarts-personal-assistant.pages.dev
set PA_E2E_BEARER_TOKEN=<entra-id-token>
set PA_E2E_EXPECTED_GITHUB_LOGIN=<github-login>
uv run pytest -m manual tests/manual/test_feature_18_report_root_capability.py -vv
```

该 probe 在真实部署环境请求一份指定历史日期的默认 source 日报，验证报告严格使用
用户给定日期，且用户可见结果包含 GitHub、Email、Calendar 的覆盖信息，并允许任一
source 以 warning 形式降级。`PA_E2E_EXPECTED_GITHUB_LOGIN` 为可选变量；配置后会强制
断言报告中的 GitHub OAuth 主体为该 login，且数据覆盖说明包含该账号可访问的全部仓库
范围。未配置时，probe 仍要求报告显示 OAuth 主体与仓库范围，或明确输出 GitHub warning。
probe 同时断言 custom SSE 中存在唯一 `report_ready` artifact，其建议文件名以 `.md` 结尾
并包含用户指定日期，`report_content` 保留 GitHub、Email、Calendar 章节且不包含凭据。
它需要部署环境已配置
Microsoft 365 OAuth、AgentArts WAT/STS 和 GitHub MCP Gateway/Target；测试本身不记录
凭据，也不进入默认 PR gate。Tool selection 的隐藏调用轨迹仍需结合部署侧 trace 检查。
