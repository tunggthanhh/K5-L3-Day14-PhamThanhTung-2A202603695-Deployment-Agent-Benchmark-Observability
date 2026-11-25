# Deployment Information

## Public URL

```text
https://k5-l3-day14-phamthanhtung-2a202603695.onrender.com
```

## Platform and verification

Render web service in Singapore, running the Docker image from `06-lab-complete`, connected to a Render Key Value instance through `REDIS_URL`. On 25 November 2026, public `/health` returned 200 (`{"status":"ok"}`), `/ready` returned 200 (`{"status":"ready"}`), and `POST /ask` without a key returned 401. The user tested an authenticated `/ask` request in the API docs and received 200 with an answer. A key appeared in a screenshot during testing and must be rotated; no key is included in this repository.

The free Render Key Value instance does not guarantee persistence across restarts, so this deployment is for the lab rather than durable production use. An earlier AWS EC2 deployment was also tested at `http://13.210.135.188:8000`; its IP may change and its HTTP endpoint must not be used to transmit secrets.

## Required environment variables

Thiết lập trên dashboard của nền tảng, không commit vào repository:

- `AGENT_API_KEY`: một secret mạnh do nền tảng hoặc người deploy tạo.
- `REDIS_URL`: URL Redis do nền tảng cung cấp.
- `PORT`: do nền tảng cấp (không cần đặt cố định nếu platform tự cấp).
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=10.0`

## Verification commands

Sau khi thay `BASE` và `AGENT_API_KEY`, bốn lệnh dưới phải lần lượt in `200`, `200`, `401`, `200`.

```bash
BASE="https://k5-l3-day14-phamthanhtung-2a202603695.onrender.com"
AGENT_API_KEY="<secret-set-on-platform>"

curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

## Screenshots to add after deployment

- `screenshots/dashboard.png`: Railway/Render deployment dashboard.
- `screenshots/running.png`: service shown as running/healthy.
- `screenshots/test.png`: four verification results above, with the secret hidden.

## Local verification already completed

The Windows run built an image of 238 MB and passed 42/42 checks it could execute, with direct SIGTERM untested on Windows. A later full Linux run on EC2 with Docker and a dedicated Redis test instance reported `PASS 12/12`, 43/43 checks. To reproduce from a Linux environment with Docker:

```bash
cd 06-lab-complete
python check_production_ready.py
```
