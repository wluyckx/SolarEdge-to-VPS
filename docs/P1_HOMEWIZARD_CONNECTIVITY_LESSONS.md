# P1 HomeWizard Connectivity Lessons Learned

Date: 2026-02-14
Scope: HA add-on -> VPS API over HTTPS with Docker + Caddy

## What Went Wrong

1. Reverse proxy pointed to the wrong upstream.
- `api.example.com` resolved to a different container than the intended API.
- Result: valid HTTP responses from the wrong app (`/health` body mismatch), misleading auth errors.

2. Ambiguous Docker DNS service names.
- Using `reverse_proxy api:8000` in a shared Docker environment can resolve to another `api` service.
- Result: Caddy forwarded traffic to the wrong stack.

3. Loopback port assumptions across containers.
- `127.0.0.1:18000` inside Caddy is Caddy itself, not host or another container.
- `host.docker.internal:18000` timed out because API was bound to `127.0.0.1:18000` on host.

4. Contract confusion (auth/header variant).
- Different API builds used different auth contracts (`Bearer` vs `X-API-Key`).
- Result: repeated 401 and misdiagnosis.

## Reliable Patterns (Use These)

1. Use unique upstream aliases.
- Give the target API a unique alias (example: `sungrow_api`) on the Docker network.
- Point Caddy to `sungrow_api:8000` instead of generic names like `api`.

2. Keep Caddy and API on the same Docker network.
- Verify both containers share at least one network.
- Avoid cross-project name collisions.

3. Validate each path hop explicitly.
- Container direct: `http://127.0.0.1:8000/health`
- Host mapping: `http://127.0.0.1:18000/health`
- Public domain: `https://<domain>/health`
- All 3 must return the same body for the same app.

4. Treat response body as identity.
- `/health` payload shape is a fast fingerprint for which app answered.
- If bodies differ, traffic is not reaching intended service.

5. Add temporary masked token diagnostics during auth incidents.
- Log token fingerprints (length + short SHA256 prefix), never raw tokens.
- Compare sender runtime fingerprint vs API runtime fingerprint.

## Standard Incident Checklist

1. Confirm expected app identity via health body.
2. Confirm Caddy upstream points to unique alias.
3. Confirm Caddy and API share network.
4. Confirm `POST /v1/ingest` appears in intended API logs.
5. Confirm auth contract in running API build (`Bearer` vs `X-API-Key`).
6. Only after 1-5, debug token value mismatch.

## Commands (Copy/Paste)

```bash
# From API container
curl -si http://127.0.0.1:8000/health

# From VPS host
curl -si http://127.0.0.1:18000/health
curl -si https://api.example.com/health

# Caddy upstream block currently loaded
docker exec caddy sh -lc "cat /etc/caddy/Caddyfile | sed -n '/api.example.com/,/}/p'"

# Which upstream does Caddy resolve?
docker exec caddy sh -lc 'wget -qO- http://sungrow_api:8000/health || true'
docker exec caddy sh -lc 'wget -qO- http://api:8000/health || true'

# Follow traffic at the intended API
docker compose logs -f api
```

## Preventive Controls

1. Reserve unique service aliases for every public upstream.
2. Never use `api` as global shared upstream name in multi-project hosts.
3. Add a startup self-check that compares expected health signature from Caddy upstream.
4. Document auth contract in one source of truth and enforce in integration tests.
