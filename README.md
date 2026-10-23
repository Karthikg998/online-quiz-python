# Online Quiz Platform

**Language:** Python (FastAPI) &nbsp;|&nbsp; **Needs:** Postgres + Redis

This is a **starter**. The application already works. Your job is everything
that gets it building, tested and running in CI.

---

## You do not need Python installed

You will build this into a container, and the container brings its own
Python 3.12. You are not being asked to extend the app — you are being asked
to ship it.

---

## 1. What this app needs

| | |
|---|---|
| **Runtime** | Python 3.12 |
| **Install dependencies** | `pip install -r requirements.txt` |
| **Start the app** | `uvicorn app.main:app --host 0.0.0.0 --port 8080` |
| **Listens on** | port 8080, bound to `0.0.0.0` |
| **Environment variables** | `DATABASE_URL`, `REDIS_URL` |
| **Needs running first** | Postgres, Redis, and the migrations applied |

### What it does

Teachers create timed quizzes. Students answer one question at a time, and the timer survives a page refresh. Scores and a per-question breakdown appear at the end.

### Endpoints

```
GET  /health
GET  /quizzes                      every quiz
POST /attempts                     {"quiz_id":1,"student":"asha"} - starts the timer
GET  /attempts/{id}                remaining time and progress
POST /attempts/{id}/answer         {"question_id":3,"choice":[1]}
POST /attempts/{id}/submit         final score and breakdown
```

`/health` reports Postgres and Redis **separately**. If it says
`postgres: false` the app started fine and your compose wiring is wrong —
do not go looking in the application code.

### Migrations

`migrations/` holds `.sql` files applied **in filename order** before the app
starts. They create the tables and insert sample data. A container running
`psql` over them in order is enough; you do not need a migration tool.

---

## 2. What you must write

| File | What it has to do |
|---|---|
| `Dockerfile` | Install dependencies **before** copying source, pin the base image, do not run as root. |
| `docker-compose.yml` | App + Postgres + Redis + a migration step, one `docker compose up`. |
| `.circleci/config.yml` | lint → unit tests → integration tests → secret scan → image build |
| Unit tests | For `app/scoring.py`. No database, no network. |
| Integration tests | Against a real Postgres and Redis as CircleCI service containers. |

Then push your image to **your own Docker Hub account**, tagged `:1.0`.

### When it works

```bash
docker compose up --build
curl localhost:8080/health
```

```json
{"status":"ok","postgres":true,"redis":true}
```

---

## Where the marks are

`app/scoring.py` is **pure logic** — plain functions over plain data, no
database and no HTTP. Start your tests there. Use pytest:
`pytest --cov=app --cov-report=term-missing`. Minimum 70%.



## Why Redis is here

The live attempt - answers so far and time remaining - is held with a TTL equal to the time limit, so an abandoned attempt expires by itself with no cleanup job.

## The hard part

A student who closes the tab and comes back must get their REMAINING time, not a fresh timer. Store the deadline, never the seconds left.

### Solution & Rationale
If the system stores a relative number like `seconds_remaining`, keeping it accurate requires ticking countdown background workers in storage or trusting client-reported timers. If the student closes the browser, disconnects, or refreshes the page, a stored duration pauses or gets wiped, allowing timer exploitation.

By storing the **immutable deadline timestamp** (`started_at + limit_seconds` in UTC) in both PostgreSQL and Redis:
1. **Stateless, deterministic calculation**: Any server instance computes `seconds_left = max(0, int((deadline - now).total_seconds()))` on the fly.
2. **Survives client refreshes and server restarts**: Real-world time elapses regardless of client connection state. If a student disconnects and returns 5 minutes later, their remaining time reflects the true elapsed duration without requiring active background timer jobs.
3. **Resilient TTL cleanup**: Redis keys use a TTL slightly longer than the quiz limit (`limit_seconds + 120`), ensuring abandoned attempts expire automatically with zero memory leaks.
4. **Fair expiration evaluation**: Network latency on submit is handled cleanly with a small grace period (`is_expired(deadline, grace_seconds=2)`) against the absolute deadline.

---

## Getting unstuck

| Symptom | Almost always |
|---|---|
| `/health` says `postgres: false` | Wrong hostname. In compose the host is the **service name**, not `localhost`. |
| Page will not load, logs fine | No `ports:` mapping, or bound to `127.0.0.1` not `0.0.0.0`. |
| `relation "..." does not exist` | Migrations did not run, or the app started before they finished. |
| Build takes minutes each time | `COPY . .` is above your dependency install. |
| CI cannot reach the database | In CircleCI service containers the host **is** `localhost` — opposite of compose. |
#hello 