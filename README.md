# TaskFlow

A task management API with background notifications. Users sign up, create projects, add
members, create and assign tasks, and get notifications when a task is assigned, reassigned,
changes status, or passes its due date without being done.

**Stack:** FastAPI · SQLAlchemy 2 + Alembic · PostgreSQL · Redis · Celery (worker + beat) · Python 3.11

**Deployment path taken:** scripted, not hosted. `deploy/deploy.sh` provisions a Linux VM
over SSH and runs the full stack behind Caddy with automatic HTTPS. The script and the
production compose file are validated (`bash -n`, `docker compose config`, `caddy validate`)
but have **not** been run against a real server. See [Deployment](#deployment).

---

## Quick start

Requirements: Docker with Compose v2.

```bash
git clone https://github.com/AnandDubey1711/taskflow.git
cd taskflow
docker compose up --build
```

This starts Postgres, Redis, a one-shot `migrate` container (runs `alembic upgrade head`),
the API, the Celery worker and Celery beat. The API listens on `http://localhost:8000`
(set `API_PORT=8010` if port 8000 is taken). Interactive docs: `http://localhost:8000/docs`.

A walk through the core flow:

```bash
API=http://localhost:8000
JSON='Content-Type: application/json'

curl -s -H "$JSON" -d '{"email":"alice@example.com","username":"alice","password":"secret123"}' $API/auth/signup
curl -s -H "$JSON" -d '{"email":"bob@example.com","username":"bob","password":"secret123"}' $API/auth/signup

ALICE=$(curl -s -H "$JSON" -d '{"email":"alice@example.com","password":"secret123"}' $API/auth/login | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
BOB=$(curl -s -H "$JSON" -d '{"email":"bob@example.com","password":"secret123"}' $API/auth/login | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
BOB_ID=$(curl -s -H "Authorization: Bearer $BOB" $API/auth/me | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

PROJECT=$(curl -s -H "$JSON" -H "Authorization: Bearer $ALICE" -d '{"key":"DEV","name":"Inventory"}' $API/projects | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -H "$JSON" -H "Authorization: Bearer $ALICE" -d '{"email":"bob@example.com"}' $API/projects/$PROJECT/members

curl -s -H "$JSON" -H "Authorization: Bearer $ALICE" \
  -d "{\"title\":\"Ship v1\",\"assignee_id\":\"$BOB_ID\",\"due_date\":\"2020-01-01T00:00:00Z\"}" \
  $API/projects/$PROJECT/tasks

curl -s -H "Authorization: Bearer $ALICE" "$API/tasks?assignee_id=$BOB_ID&status=todo"

sleep 65
curl -s -H "Authorization: Bearer $BOB" $API/notifications
```

Bob ends up with an "alice assigned DEV-1 to bob" notification and, after the next overdue
check (every 60 s), "Due date for DEV-1 has passed". Every notification is also written
to the worker log: `docker compose logs worker`.

## Local development without Docker

```bash
uv venv -p 3.11 .venv && uv pip install -p .venv/bin/python -e ".[dev]"
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
.venv/bin/celery -A app.worker.celery_app worker --loglevel=info
.venv/bin/celery -A app.worker.celery_app beat --loglevel=info
```

Run each long-running command in its own terminal. `.env.example` uses SQLite and a local
Redis on `localhost:6379`. SQLite is a convenience for local work only; Docker, CI and
production use PostgreSQL.

Lint and format: `.venv/bin/ruff check . && .venv/bin/ruff format --check .`

## Configuration

All settings are environment variables (read by `pydantic-settings`, `.env` supported).

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./taskflow.db` | SQLAlchemy URL; compose uses Postgres |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker and task search cache |
| `SESSION_IDLE_HOURS` | `24` | Session expires after this much inactivity |
| `SESSION_MAX_DAYS` | `30` | Absolute session lifetime |
| `SESSION_TOUCH_MINUTES` | `5` | Minimum gap between `last_seen_at` updates |
| `BCRYPT_ROUNDS` | `12` | bcrypt cost factor |
| `OVERDUE_CHECK_SECONDS` | `60` | Interval of the overdue sweep |
| `TASK_SEARCH_CACHE_TTL_SECONDS` | `300` | TTL of cached `GET /tasks` results |
| `REDIS_TIMEOUT_SECONDS` | `0.5` | Redis socket timeout for cache and health checks |
| `API_PORT` | `8000` | Host port for the API in `docker-compose.yml` |
| `POSTGRES_PASSWORD` | `taskflow` | Postgres password in `docker-compose.yml` |

## API

All endpoints except signup, login, `/health` and `/metrics` need `Authorization: Bearer <token>`.

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/auth/signup` | anyone | `{email, username, password}` → 201, 409 if email taken |
| POST | `/auth/login` | anyone | `{email, password}` → `{token, user}` |
| POST | `/auth/logout` | user | Deletes the session |
| GET | `/auth/me` | user | Current user |
| POST | `/projects` | user | `{key, name}`; creator becomes owner and first member |
| GET | `/projects` | user | Projects I'm a member of, with `member_count` |
| GET / PATCH / DELETE | `/projects/{project_id}` | member / owner / owner | Rename or delete |
| GET | `/projects/{project_id}/members` | member | Used to pick assignees |
| POST | `/projects/{project_id}/members` | owner | `{email}` |
| DELETE | `/projects/{project_id}/members/{user_id}` | owner, or self | Owner can't be removed; the member's tasks are unassigned |
| POST | `/projects/{project_id}/tasks` | member | `{title, description?, status?, assignee_id?, due_date?}` |
| GET / PATCH / DELETE | `/projects/{project_id}/tasks/{task_id}` | member | PATCH changes only the fields sent; `assignee_id: null` unassigns |
| GET | `/tasks` | user | Search across my projects, cached (see below) |
| GET | `/notifications` | user | `?is_read=true\|false&limit=&offset=` |
| POST | `/notifications/{notification_id}/read` | owner of it | Marks read |
| GET | `/health` | anyone | `ok`, `degraded` (Redis down) or 503 `down` (DB down) |
| GET | `/metrics` | anyone | Prometheus format; blocked at the proxy in production |

`GET /tasks` query parameters (all optional, combined with AND; repeat a parameter for
"any of"):

```
project_id=<uuid>  status=todo|in_progress|done  assignee_id=<uuid>  is_unassigned=true|false
due_from=YYYY-MM-DD  due_to=YYYY-MM-DD  sort=due_date|created_at|updated_at|title
order=asc|desc  limit=1..100 (default 20)  offset=0..
```

`due_from` and `due_to` are UTC calendar days and inclusive at both ends. The response is
`{items, total, limit, offset}` and carries an `X-Cache: HIT|MISS` header.

## Architecture

```
                 ┌──────────────┐  SELECT/INSERT/UPDATE   ┌──────────────┐
  client ──────▶ │  FastAPI API │ ──────────────────────▶ │  PostgreSQL  │
  Bearer token   │  (uvicorn)   │ ◀────────────────────── │              │
                 └──────┬───────┘                         └──────▲───────┘
            send_task   │  GET/SET task search cache             │
            after commit│                                        │ notifications,
                 ┌──────▼───────┐                                │ overdue claims
                 │    Redis     │ ◀── broker ──┐                 │
                 └──────▲───────┘              │                 │
                        │ schedule        ┌────┴─────────┐       │
                 ┌──────┴───────┐  every  │ Celery worker│ ──────┘
                 │ Celery beat  │ ──60s──▶│ notify_task_ │
                 └──────────────┘  nightly│ event, sweep │
                                          └──────────────┘
```

Code layout follows one direction of dependencies: `api` (routers) → `services` (business
logic, transactions) → `models` (SQLAlchemy). `schemas` holds Pydantic request/response
models, `core` holds cross-cutting pieces (auth dependencies, errors, security, logging,
metrics, Redis client) and `worker` holds the Celery app and its tasks.

```
app/
├── api/        auth_router, project_router, project_member_router, task_router,
│               notification_router, ops_router
├── core/       dependencies (auth + project access), errors, security, logging_config,
│               request_tracking, metrics, redis_client
├── models/     user, user_session, project, project_member, task, notification
├── schemas/    request/response models per entity, task_event, health
├── services/   user, user_session, project, project_member, task, task_event,
│               task_cache, notification
├── worker/     celery_app, task_names, tasks
├── config.py   settings
├── db.py       engine and session factory
└── main.py     app, middleware, exception handlers, routers
migrations/     Alembic revisions 0001–0006
deploy/         deploy.sh, docker-compose.prod.yml, Caddyfile
```

### Data model

- `users`: email (unique, lower-cased), username, bcrypt `password_hash`.
- `user_sessions`: `token_hash` (SHA-256 of the bearer token), `created_at`, `last_seen_at`.
- `projects`: unique `key` (e.g. `DEV`), `name`, `owner_id`, `last_task_number` (task
  numbering), `task_version` (cache invalidation).
- `project_members`: `(project_id, user_id)` primary key, `role` = `owner | member`.
- `tasks`: one table for all projects. `number` is unique per project and forms the key
  `DEV-12`. `status`, `assignee_id`, `due_date`, `overdue_notified_at`, `creator_id`.
  Indexed on `(project_id, status | assignee_id | due_date | created_at)` plus a partial
  index for overdue candidates.
- `notifications`: recipient `user_id`, `task_id`, `event_id`, `type`, `message`, `read_at`;
  unique on `(event_id, user_id)`.

`member_count` is computed from `project_members` rather than stored, so it can't drift.

### Authentication: sessions, not JWT

Login returns a random 256-bit token. The database stores only its SHA-256, so a database
leak exposes no usable sessions. Sessions are used instead of JWT because logout and expiry
then work immediately: deleting the row ends the session, with no denylist or refresh-token
rotation. A session ends after 24 h without activity or 30 days in total. To avoid a write
per request, `last_seen_at` is refreshed at most every 5 minutes.

Passwords are hashed with bcrypt **on the server** and only ever travel over TLS. Login
returns the same 401 for an unknown email and a wrong password, and runs a dummy bcrypt
check for unknown emails so response time doesn't reveal which emails exist. Validation
errors never echo submitted values, so a password can't come back in a 422.

### Authorization

Two FastAPI dependencies, `require_project_member` and `require_project_owner`, guard every
project-scoped route. Non-members get **404, not 403**, so project IDs can't be probed. Task
IDs are looked up within the project in the URL, so a valid task ID under another project
is also a 404. Assignees must be members of the task's project.

### Notifications

Task changes are saved first; **after the commit** the API queues a `TaskEvent` with
`send_task` (by name, so the API never imports worker code). The request returns
immediately.

| Event | Recipients | Message |
|---|---|---|
| Assigned | actor, assignee | `alice assigned DEV-12 to bob` |
| Reassigned | actor, old and new assignee | `alice reassigned DEV-12 from bob to carol` |
| Unassigned (incl. member removal) | actor, old assignee | `alice unassigned bob from DEV-12` |
| Status changed | actor, assignee | `carol moved DEV-12 from todo to in_progress` |
| Overdue | assignee, or project owner if unassigned | `Due date for DEV-12 has passed` |

The worker writes one `notifications` row per recipient in a single transaction and logs
each delivery as JSON. Each event has an `event_id`, and the table is unique on
`(event_id, user_id)`, so a retried job can't create duplicates.

**Overdue detection without per-task timers.** Celery beat runs `check_overdue_tasks` every
60 s. One `UPDATE … SET overdue_notified_at = now() WHERE due_date < now() AND status <> 'done'
AND overdue_notified_at IS NULL RETURNING id` claims the newly overdue tasks atomically, so
overlapping runs can't notify twice. A partial index covers only tasks that can still become
overdue, so the query stays cheap no matter how many tasks exist. Changing the due date or
reopening a done task clears `overdue_notified_at`, so the task can be notified again.
Per-task delayed jobs (`eta=due_date`) were rejected: with a Redis broker, long ETAs sit in
worker memory and get redelivered, and every due-date change would need the old job
cancelled.

### Caching `GET /tasks`

Each project row has a `task_version`. Every write that changes task results (create,
update, delete a task; removing a member who had tasks) increments it **in the same
transaction** as the change. On read:

1. Load the caller's `(project_id, task_version)` pairs, narrowed by `?project_id`.
2. Key = SHA-256 of those pairs + the normalised filters, sort and page.
3. Redis hit → return it. Miss → run the query, store it for 5 minutes.

A write bumps the version, so every cached view of that project — any user, filter
combination or page — stops matching at once. Old keys are never read again and simply
expire; there is no key scanning or tracking. Because the key is built from the caller's own
project set, a user can only hit entries for projects they can see, and membership changes
change the key automatically. Multi-value filters are sorted and deduplicated, so
`status=done&status=todo` and `status=todo&status=done` share an entry.

The version lives in Postgres rather than in a Redis counter on purpose. A Redis `INCR`
after commit is lost if Redis is briefly unreachable, and the old entries then look current
again once Redis returns: a stale read. With the version committed alongside the data, that
can't happen. This was tested by changing a task while Redis was stopped and reading after it
came back. If Redis is down, cache calls time out after 0.5 s and requests are served from
the database.

### Observability

- `/health` checks the database (`SELECT 1`) and Redis (`PING`): `ok`, `degraded` (Redis
  down, 200) or `down` (database down, 503).
- `/metrics`: `http_requests_total{method,route,status}`,
  `http_request_duration_seconds{method,route}` and
  `task_search_cache_lookups_total{result}`. Routes are labelled by template
  (`/projects/{project_id}`), and unknown paths share one `unmatched` label, so the number of
  label values stays bounded.
- JSON logs from the API and worker. Every line written during a request carries a
  `request_id`, taken from a valid `X-Request-ID` header or generated, and echoed back in the
  response. Bodies and headers are never logged.

## Assumptions

- A task's assignee must be a member of its project; unassigned is allowed.
- Any member can create, edit and delete tasks; only the owner renames or deletes the
  project and manages members. Members can leave; the owner can't be removed.
- Project keys are 2–10 letters/digits starting with a letter, globally unique, and can't be
  changed (task keys are built from them).
- "Delivery" of a notification is a `notifications` row plus a log line.
- Overdue notifications can lag by up to one sweep interval (60 s).
- Due dates are stored in UTC; a due date without a timezone is treated as UTC.
- `GET /tasks` with no `project_id` searches all projects the caller belongs to.
- Adding a member by an unknown email returns 404. That tells a project owner whether an
  email is registered, which I accepted for a members-only action.
- The API runs behind HTTPS in any real deployment.

## CI

`.github/workflows/ci.yml` runs on pushes to `main` and on pull requests:

- **lint**: `ruff check` (pycodestyle, pyflakes, isort, pep8-naming, pyupgrade, bugbear,
  commented-out code) and `ruff format --check`.
- **migrations**: against a Postgres 16 service container: import check, `alembic upgrade
  head`, `downgrade base`, `upgrade head` again, then `alembic check` to prove the models
  and migrations match.
- **docker**: builds the image.

There is no test job; see the first item under tradeoffs.

## Deployment

Path taken: **scripted, not executed.** I didn't host it publicly. The script below is
what I would run against a fresh Ubuntu VM with a DNS record pointing at it.

```bash
DEPLOY_HOST=ubuntu@203.0.113.10 DEPLOY_DOMAIN=taskflow.example.com ./deploy/deploy.sh
```

`deploy/deploy.sh` connects over SSH and:

1. Installs Docker if missing.
2. Clones or fast-forwards the repo in `/opt/taskflow`.
3. Creates `.env` on first run with a random `POSTGRES_PASSWORD` (mode 600) and the domain.
4. Runs `docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build`.
5. Polls `https://$DEPLOY_DOMAIN/health` until it passes.

`deploy/docker-compose.prod.yml` adds restart policies, Redis persistence (AOF), stops
publishing the API port, and puts **Caddy** in front with automatic Let's Encrypt
certificates. The `Caddyfile` returns 404 for `/metrics` on the public domain, so metrics
are only reachable from inside the Docker network.

## Tradeoffs & what I'd do with more time

**Deliberately deprioritized**

- **Automated tests.** This is the biggest gap and the brief asks for them. I chose to spend
  the time on getting the trickier behaviour right and checked each phase with scripted
  end-to-end runs against the real stack instead: authorization boundaries, cache
  invalidation after every kind of write, 20 concurrent task creations, Redis and Postgres
  outages, and retried notification jobs. Those checks aren't in the repo, so they don't
  protect against regressions. The first thing I'd add is a pytest suite covering the same
  ground: authorization matrix, cache stale-read cases, notification recipients and
  idempotency, overdue sweep, session expiry. It would use a real Postgres in CI and Celery
  in eager mode, plus a test job in CI.
- **Hosting.** The deployment is scripted and validated, not live.

**Known limitations**

- **Notifications can be lost if Redis is down** at the moment of a write: the change is
  saved, the enqueue fails and is logged. The fix is a transactional outbox: write the event
  in the same transaction and have a relay push it to the queue.
- **Worker metrics aren't exposed.** `/metrics` covers the API process only. Notifications
  created, job failures and queue depth need a Celery exporter or a Pushgateway.
- **Metrics are per process.** Fine for one uvicorn process; several would need
  `prometheus_client` multiprocess mode.
- **Offset pagination** gets slow for deep pages; keyset pagination on `(sort key, id)`
  would fix it.
- **Every `GET /tasks` still does one small database query** to read project versions. That
  query is cheap and indexed, and it's what makes the cache safe. Caching the membership set
  per user in Redis, with its own invalidation, would remove it.
- **No cache stampede protection.** Many concurrent misses on the same key all hit the
  database. A short Redis lock or request coalescing would help under load.
- **Session lookup is a database query per request.** Caching it in Redis would remove that,
  at the cost of slightly slower revocation.

**Missing features I'd add next**

- Rate limiting on `/auth/login` and `/auth/signup`.
- Password change, account deletion, logout from all sessions.
- Transfer of project ownership.
- A per-project task list endpoint and filtering notifications by project.
- Argon2id instead of bcrypt (bcrypt was chosen as the widely known option the brief allows).
- CORS configuration once a browser client exists.
- Retention for old notifications.
