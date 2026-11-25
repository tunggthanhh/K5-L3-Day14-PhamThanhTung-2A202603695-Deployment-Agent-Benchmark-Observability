# Day 14 Lab — Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

1. Hard-code configuration or a secret makes rotation unsafe and prevents one image from serving multiple environments.
2. Keeping state in process memory loses it after restart and breaks horizontal scaling.
3. No liveness/readiness probes means an orchestrator cannot distinguish a live process from one ready for traffic.
4. Default text logs are difficult to filter and correlate across services; JSON structured logs make fields queryable.
5. Abrupt process termination can drop in-flight requests; the service needs graceful SIGTERM handling.
6. Calling an upstream LLM without request limits or a budget guard can cause abuse and uncontrolled spending.

Concrete examples in the supplied starter: `01-localhost-vs-production/develop/app.py:17?18` hardcodes demo credentials; line 34 prints the fake API key; lines 51?53 bind localhost, fix port 8000 and enable reload. The advanced sample uses `settings.host` and `settings.port` (`production/app.py:196?197`), and defines `/health` (`production/app.py:135`). The credentials in the starter are explicitly fake examples.

### Exercise 1.2: Local test result

Using FastAPI TestClient against `01-localhost-vs-production/develop/app.py`, `POST /ask?question=Hello` returned HTTP 200 and a mock answer. This is an in-process HTTP test, not a network deployment. The starter uses a query parameter; the final Part 6 implementation uses a JSON body. The starter also printed its explicitly fake hardcoded demo key in debug logs, illustrating the secret-logging anti-pattern.

### Exercise 1.3: Develop vs production

| Feature | Develop | Production | Why important |
|---|---|---|---|
| Configuration | Convenient local defaults | Environment variables | One artifact can run in dev/staging/prod without editing code. |
| Secrets | Often local/demo values | Injected secret at runtime | Prevents credential leakage and supports rotation. |
| State | May be memory-local | Redis-backed | Instances remain stateless and can scale horizontally. |
| Health | Process-only feedback | `/health` + `/ready` | Separates liveness from dependency readiness. |
| Shutdown | Manual stop | Uvicorn graceful shutdown | Lets in-flight requests finish. |
| Logging | Human-readable console | JSON event logs | Enables search, metrics correlation and alerting. |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

The questions refer to `02-docker/develop/Dockerfile`:

1. The base image is `python:3.11` (full Python image).
2. The working directory is `/app`.
3. Copying `requirements.txt` before the application allows Docker to reuse the dependency-install layer when application code changes but dependencies do not.
4. `ENTRYPOINT` defines the container's main executable; `CMD` supplies its default arguments, or the default command when no entrypoint is defined. Runtime arguments can override CMD.

The final Part 6 project uses a different multi-stage Dockerfile based on `python:3.11-slim`.

### Exercise 2.2: Run the Docker examples

On EC2, both built example containers were started on loopback-only ports and `/health` was requested over HTTP. The develop container returned HTTP 200 with `status: ok` and `container: true`; the production container returned HTTP 200 with `status: ok` and `version: 2.0.0`. Both temporary containers were stopped after the test.

### Exercise 2.3: Example image comparison

Built the two `02-docker` Dockerfiles on Linux EC2 and measured `docker image inspect` `Size` (decimal MB): develop **426.32 MB** (426,319,482 bytes), production **57.41 MB** (57,408,303 bytes), a **86.53% reduction**. The multi-stage production image keeps installed runtime dependencies while leaving build tools in the builder stage; its slim base also contributes to the reduction. These are daemon-reported image sizes for this build, not disk usage on Windows.

### Exercise 2.3: Final-project image measurement

The full checker built the final image successfully at **238 MB**, below the 500 MB requirement. It is multi-stage, runs as a non-root user, and exposes a Docker `HEALTHCHECK` for `/health`.

### Exercise 2.4: Stack design

`docker-compose.yml` defines two services: `agent` is built from the project Dockerfile and depends on a healthy `redis` service. `REDIS_URL=redis://redis:6379/0` connects the agent to Redis. Redis persists data in the `redis-data` volume.

## Part 3: Cloud Deployment

### Railway/Render configuration

Both platform manifests are included in `06-lab-complete/`:

- `railway.toml` selects the Dockerfile builder and uses `/health` as the health check path.
- `render.yaml` defines a Docker web service, a `/health` check, generated `AGENT_API_KEY`, and a separately supplied `REDIS_URL`.

Railway uses a TOML deploy configuration managed with the Railway service. Render uses a Blueprint YAML service declaration. Both must receive secrets from their platform environment-variable settings, not source code.

### Exercise 3.3: Cloud Run CI/CD pipeline

`cloudbuild.yaml` builds a container image, tags/pushes it to Artifact Registry, then deploys it to Cloud Run. `service.yaml` describes the running Cloud Run service, including its container and runtime settings. Cloud Build supplies the repeatable CI/CD execution; Cloud Run receives the immutable image and manages HTTPS/scaling. Secrets should be connected through platform configuration rather than baked into the image.

### Deployment status

The Part 6 agent is deployed on Render at `https://k5-l3-day14-phamthanhtung-2a202603695.onrender.com` with a Render Key Value Redis-compatible service. On 25 November 2026, `/health` and `/ready` returned 200, `/ask` without a key returned 401, and the user verified an authenticated `/ask` request returned 200 in the API documentation. Dashboard and test screenshots still need to be added to the repository. A key was exposed in a testing screenshot and must be rotated.

## Part 4: API Security

### Exercise 4.2?4.3: JWT and sliding window test

Using FastAPI TestClient against `04-api-gateway/production/app.py` (in process), a request without a bearer token returned 401. `POST /auth/token` with the provided demo student account returned 200; the token was used without saving it to the report. Eleven authenticated requests returned:

```text
200 200 200 200 200 200 200 200 200 200 429
```

The demo uses a per-user sliding window of timestamps: 10 requests per 60 seconds for a user and 100 for an admin. Admins have a higher limit, not an unlimited bypass. Its limiter is in memory and is unsuitable for shared state across instances; the final Part 6 limiter uses Redis. The demo signs JWTs with HS256 and checks signature and expiry before accepting a request.


The final agent was exercised by `check_production_ready.py` with these verified outcomes:

| Control | Result |
|---|---|
| Missing or invalid `X-API-Key` | HTTP 401 |
| Valid API key | HTTP 200 |
| Per-key rate limit | HTTP 429 after the configured limit; state survives agent restart because it is in Redis |
| Exhausted budget | HTTP 402 |

Rate limiting protects availability by limiting request frequency. The cost guard protects spend by retaining the accumulated estimated cost in Redis and rejecting further requests once the configured daily budget is reached. Both controls are needed because a low-rate client can still consume excessive expensive tokens, while a budget-only control does not stop traffic bursts.

## Part 5: Scaling & Reliability

### Exercise 5.4: Three-instance stateless test

On EC2, I ran the supplied `05-scaling-reliability/production` Compose stack with three agent replicas, Redis and Nginx, binding the test port to loopback. `python3 test_stateless.py` sent five requests in the same session; Nginx routed them to **three distinct instances**, and the final history contained **10 messages** (five user messages and five responses). This demonstrates that the tested session history was shared across those replicas through Redis. The isolated test project was stopped after the test.


- `/health` is a liveness endpoint and stays 200 while the process runs, including when Redis is unavailable.
- `/ready` is a readiness endpoint and returns 503 when Redis is unavailable, so a load balancer can stop sending traffic to an unready instance.
- Rate-limit and cost state are stored in Redis rather than memory, so restarts and multiple workers share the same state.
- The FastAPI lifespan hook logs startup/shutdown; Uvicorn/Docker stop was verified to exit cleanly in 1.2 seconds.

## Part 6: Production-readiness verification

Full verification on this Windows host completed **42/42 individual checks**. Docker build, image size, runtime health, readiness, auth, Redis rate-limit persistence, budget guard, environment configuration, JSON logging, and Docker graceful stop all passed.

The full checker was run on EC2 Linux using Python 3.11, Docker CLI and Compose, with a separate Redis test instance. It returned:

```text
📋 Checklist Deliverable
   ✅ Dockerfile (multi-stage, < 500 MB)
   ✅ docker-compose.yml (agent + redis)
   ✅ .dockerignore
   ✅ Health check endpoint (GET /health)
   ✅ Readiness endpoint (GET /ready)
   ✅ API Key authentication
   ✅ Rate limiting
   ✅ Cost guard
   ✅ Config từ environment variables
   ✅ Structured logging
   ✅ Graceful shutdown
   ✅ Public URL ready (Railway / Render config)
Result: 12/12 tiêu chí đạt · 43/43 checks passed
🎉 PASS 12/12 — PRODUCTION READY!
```

The built image measured 56 MB in that Docker environment. The in-flight request completed with HTTP 200 after SIGTERM and the process exited with code 0. Docker stop completed in 1.3 seconds.

## AI assistance log

AI assistance was used to inspect the provided starter project, implement the Part 6 TODOs, execute the readiness checker, run local Part 7 load/eval benchmarks, and prepare this report. All reported measured values came from generated JSON checker/benchmark output in this repository.
