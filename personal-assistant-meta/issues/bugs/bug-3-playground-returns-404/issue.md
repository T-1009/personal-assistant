---
status: backlog
related: feat/web-chat-frontend
discovered_by: personal-assistant-e2e-tester
discovered_at: 2026-06-08 E2E test session for Feature 1.1
---

# Bug 3: /playground Endpoint Returns 404 — Chainlit Not Mounted

## 现象 (Symptoms)

The `/playground` endpoint returns **404 Not Found** with `application/json` content type. The implementation plan and task description state that "Chainlit /playground is still served at /playground", but no Chainlit mount is registered in `main.py`.

The comment in `main.py` (line 102-103) says:
> `Chainlit /playground will not be shadowed — just register them before this line.`

However, the Chainlit mount has not been registered. The SPA fallback (which is also broken — see bug-2) cannot serve as a substitute.

### Evidence

```bash
# Service running with dist/ mounted
GET /playground → 404 Not Found (application/json)
GET /playground/ → 404 Not Found (application/json)
GET / → 200 OK (serves index.html correctly)
GET /api/ping → 200 OK (API works)
```

## 复现步骤 (Reproduction Steps)

1. Run `npm run build` in `personal-assistant-client/` to generate `dist/`
2. Start the service: `uv run uvicorn app.main:app --port 8765` with `MAAS_API_KEY=dummy`
3. `GET http://127.0.0.1:8765/playground`
4. Observe: **404 Not Found** (expected: 200 or 302 — a valid response, not 404)

## 预期 vs 实际 (Expected vs Actual)

| 场景 | 预期行为 | 实际行为 |
|------|---------|---------|
| GET /playground | 200 or 302 (Chainlit serves its UI) | 404 Not Found |
| GET /playground/ | 200 or 302 | 404 Not Found |
| GET / | 200 OK, serves assistant-ui | 200 OK ✅ |

## 环境 (Environment)

- Feature branch: `feat/web-chat-frontend`
- FastAPI/Starlette versions: as per `uv.lock`
- Chainlit: not installed in the venv (`chainlit` binary not found in `.venv/bin/`)
- E2E test session: Feature 1.1 E2E test run on 2026-06-08

## 影响 (Impact)

- **Blocking**: No — Chainlit was not part of Feature 1.1's scope (the feature was about assistant-ui integration). However, if `/playground` was expected to remain functional after the static mount change, this represents a regression.
- **Affected flows**:
  - Accessing the Chainlit /playground interface (future feature)
  - The `/playground` path is now shadowed — it returns 404 instead of a Chainlit page

## 备注 (Note)

This may be a design gap rather than an implementation bug. The `/playground` path is referenced in implementation documentation as something that should coexist with the web chat frontend. However:
1. Chainlit is not installed as a dependency
2. No Chainlit mount is registered in `main.py`
3. The comment implies it should be registered "before this line" (before the StaticFiles mount)

If Chainlit integration is planned for a future feature, this bug can be resolved by that feature. If `/playground` was expected to work now, the Chainlit mount needs to be added.
