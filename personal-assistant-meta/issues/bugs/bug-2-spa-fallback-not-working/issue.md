---
status: backlog
related: feat/web-chat-frontend
discovered_by: personal-assistant-e2e-tester
discovered_at: 2026-06-08 E2E test session for Feature 1.1
---

# Bug 2: SPA Fallback Not Working (StaticFiles html=True)

## 现象 (Symptoms)

The `StaticFiles` mount in `main.py` uses `html=True` with the documented intent of enabling SPA fallback (client-side routing). However, accessing any path that doesn't correspond to a physical file in `dist/` — such as `/chat`, `/settings`, or any client-side route — returns **404 Not Found** instead of serving `index.html`.

The comment in `main.py` (line 106) states:
> `html=True: enables SPA fallback — any path not matching a physical file serves index.html, allowing React Router (or equivalent) to handle client-side routing.`

This comment is incorrect for Starlette 1.2.1. The `html=True` parameter in Starlette's `StaticFiles` only serves `index.html` from a matching directory path (e.g., `/chat/` → tries `dist/chat/index.html`). It does **NOT** perform root-level `index.html` fallback for arbitrary paths.

### Evidence

```bash
# Service running with dist/ mounted
GET /chat → 404 Not Found (application/json)
GET /playground → 404 Not Found (application/json)
GET / → 200 OK (serves index.html correctly)
```

The 404 responses have `content-type: application/json` (FastAPI's default 404 handler), confirming the StaticFiles middleware is not handling these paths.

## 复现步骤 (Reproduction Steps)

1. Run `npm run build` in `personal-assistant-client/` to generate `dist/`
2. Start the service: `uv run uvicorn app.main:app --port 8765` with `MAAS_API_KEY=dummy`
3. `GET http://127.0.0.1:8765/chat`
4. Observe: **404 Not Found** (expected: 200 with index.html)

## 预期 vs 实际 (Expected vs Actual)

| 场景 | 预期行为 | 实际行为 |
|------|---------|---------|
| GET /chat | 200 OK, serves index.html (SPA fallback) | 404 Not Found |
| GET /settings | 200 OK, serves index.html | 404 Not Found |
| GET / | 200 OK, serves index.html | 200 OK ✅ |

## 环境 (Environment)

- Feature branch: `feat/web-chat-frontend`
- Starlette version: 1.2.1
- FastAPI version: (latest via uv.lock)
- E2E test session: Feature 1.1 E2E test run on 2026-06-08

## 影响 (Impact)

- **Blocking**: No — the root page (`/`) works correctly, and the application can function as long as users always start from `/`. However, direct navigation to client-side routes (e.g., bookmarking `/chat`) will fail.
- **Affected flows**: 
  - Direct URL navigation to any client-side route
  - Browser refresh on a client-side route
  - The assistant-ui client-side routing (via `@assistant-ui/react`) cannot be used with URL-based navigation

## 修复建议 (Fix Direction)

A catch-all route should be registered **before** the `StaticFiles` mount:

```python
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Only fall back to index.html for non-API, non-asset paths
    if full_path.startswith("api/") or full_path.startswith("assets/"):
        raise HTTPException(status_code=404)
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404)
```

Or consider using `Mount` with a custom SPA fallback ASGI app.
