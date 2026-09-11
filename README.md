# Final Third API

Development API using Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic
and PostgreSQL 17. Dependencies are locked with uv.

## Start

Run from this `api/` directory. Requires Docker Engine/Desktop with Compose v2
and Make; Python does not need to be installed on the host.

On Fedora with the distribution's `docker-cli`/`moby-engine` packages, Compose is
a separate package: `sudo dnf install docker-compose`. Check `docker compose version`
before starting. If Docker reports `unknown flag: --build` or `unknown command:
docker compose`, the Compose plugin is missing; `--build` is a valid Compose flag.
Start the daemon with `sudo systemctl start docker` if `docker info` reports a
missing socket or stopped daemon.

```bash
cp .env.example .env  # optional; the defaults work out of the box
make up
```

For a live deployment, combine the base file with the production override:

```bash
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

Set `AUTH_SECRET`, `POSTGRES_PASSWORD`, and `OBJECT_STORAGE_SECRET_KEY` through
the deployment secret store before starting. The production entrypoint refuses
development defaults, startup seeding, and Uvicorn reload mode. Put TLS,
HTTP security headers, and public routing in front of the API and web service;
do not expose PostgreSQL or MinIO directly to the internet.

Open http://localhost:8000/docs for interactive API docs. PostgreSQL is available
at `localhost:5432`; the default database/user is `final_third` and the local-only
password is `final_third_dev`. Both published ports bind to loopback.

Compose waits for PostgreSQL's health check. Every API container start applies
`alembic upgrade head`, adds missing demo data, then starts Uvicorn with hot reload.
Failed migrations or seeding stop startup. Data persists in a named volume across
stops and rebuilds. Seeding runs in one transaction and never overwrites existing
rows. Set `SEED_ON_STARTUP=false` in `.env` to disable automatic demo data.

Edit `src/api/` and Uvicorn reloads automatically through the source bind mount.
There is no rebuild needed for Python edits. If filesystem events are unreliable,
set `WATCHFILES_FORCE_POLLING=true` in `.env` and run `make up` to recreate the API.
Dependency changes require `uv lock` and `make up`. Changes to `.env` also require
`make up`; `make restart` does not reload container environment variables.

## Commands

| Command | Action |
| --- | --- |
| `make up` | Build and start in the background, waiting for health checks |
| `make down` | Stop the stack, preserving the database |
| `make logs` | Follow logs (Ctrl-C only stops following) |
| `make restart` | Restart the API, migrate and seed again |
| `make seed` | Insert missing demo rows without changing existing rows |
| `make db-reset` | **Delete this Compose project's database volume**, then start fresh |
| `make db-shell` | Open PostgreSQL's SQL console |
| `make migration message="add fixtures"` | Generate a migration from model changes |
| `make migrate` | Apply pending migrations |
| `make test` | Run the tests against a temporary PostgreSQL database |
| `make lint` | Check Python lint and formatting |

`make db-reset` reseeds with the default `SEED_ON_STARTUP=true`. If automatic
seeding is disabled, run `make seed` afterward when you want demo records.
Normal `make down` never removes the database volume. Changing PostgreSQL's
initial user/password/database variables does not update an existing volume;
reset the disposable development database to apply those changes.

Podman users with a Compose provider can override the command, for example
`make up COMPOSE="podman compose"`. Bind mounts use `:Z` for SELinux hosts.

## Initial scope

The first migration creates `clubs`, `club_domains`, and club-owned `teams`, with
foreign keys and uniqueness constraints. The UUID migration gives each record an
explicit primary key: `club_id`, `club_domain_id`, or `team_id`. PostgreSQL generates
UUIDs for new records, and all `club_id` foreign keys are UUIDs too. Seeds include
Montpellier FC and Oakwood United, their domains, and Under 12s/Under 14s teams.
Montpellier also includes the seeded `Montpellier (Cheltenham) 1st` team linked to
FA Full-Time team ID `248931689`.

### FA Full-Time integration

The team mapping is stored as external identity metadata so fixture imports can be
added without coupling the application name to the provider's display name. The
current public source is the team's Full-Time HTML page:
`https://fulltime.thefa.com/displayTeam.html?teamID=248931689`.

Full-Time provides public team/league pages and live score entry through its own
Matchday app, but no documented public fixtures API was identified. The next
integration step should therefore be a small provider adapter that fetches and
parses the public page on a scheduled job, with source IDs and last-seen timestamps
on imported fixtures. It should not scrape on every page request.
Seeding preserves existing UUIDs; resetting the database generates new ones.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Process liveness |
| `GET /health/ready` | Database connectivity (503 if unavailable) |
| `GET /api/v1/public/clubs/resolve?hostname=montpellier-fc.localhost` | Resolve public club identity by registered hostname |
| `GET /api/v1/public/clubs/{club_id}/teams` | Public teams, using the UUID returned by the club lookup |
| `GET /api/v1/clubs/{club_id}/players` | Authenticated, role-aware player directory |
| `GET /api/v1/clubs/{club_id}/payments` | Role-aware club payment records |
| `POST /api/v1/clubs/{club_id}/payments` | Admin payment record creation |
| `PATCH /api/v1/clubs/{club_id}/payments/{payment_id}` | Admin payment status update |
| `GET /api/v1/clubs/{club_id}/documents` | Authenticated, role-aware document list |
| `POST /api/v1/clubs/{club_id}/documents` | Admin private document upload |
| `DELETE /api/v1/clubs/{club_id}/documents/{document_id}` | Admin document deletion |
| `GET /api/v1/clubs/{club_id}/fixtures` | Authenticated club fixtures |
| `POST /api/v1/clubs/{club_id}/fixtures` | Coach/admin fixture creation |
| `GET /api/v1/clubs/{club_id}/fixtures/{fixture_id}/availability` | Role-aware availability responses |
| `PUT /api/v1/clubs/{club_id}/fixtures/{fixture_id}/availability` | Create or update a child's response |
| `POST /api/v1/auth/register` | Create an account and return an access token |
| `POST /api/v1/auth/login` | Authenticate with an email and password |
| `GET /api/v1/auth/me` | Return the authenticated account (`Authorization: Bearer ...`) |

`hostname` accepts a hostname without a scheme or port; case and a final dot are
normalized. Resolve a hostname first, then copy the returned `club_id` UUID into
the teams endpoint. Club slugs such as `montpellier-fc` are human-readable labels;
they are not IDs. Invalid UUID path parameters return 422; unknown UUIDs return 404.
Responses use snake_case and UUID strings. The frontend still uses its existing demo
data; connecting it to these endpoints is a separate step. Badge paths currently
refer to frontend assets. Club themes remain in the frontend.

Authentication provides account registration, login, and a protected current-user
endpoint. Passwords are stored as PBKDF2-HMAC hashes and access tokens are signed,
expiring bearer tokens. Users are related to clubs through `club_memberships`,
whose roles are `member`, `coach`, `admin`, or `owner`; `/api/v1/auth/me` includes
the authenticated user’s memberships. The development seed creates Sophie,
Jordan, and Casey with the fixture memberships and passwords in `src/api/seed.py`.
Set a strong `AUTH_SECRET` outside development. Players, payments and other
private records are not exposed yet; before adding them, enforce membership/role
checks and database-level tenant scope. A domain lookup or supplied club ID is
never authorization. CORS origins are an explicit JSON list in `.env`.

Player records are club-scoped and include the compliance fields needed for an FA
registration workflow: legal name, date of birth, FA number, registration status,
and consent status. The player directory requires an authenticated club
membership. Owners, admins, and coaches can see the club's player directory;
ordinary members only receive players linked to them through `player_guardians`.
This parent/guardian relationship must also scope future fixtures, availability,
registration, and document endpoints.

FA Full-Time imports are handled by the separate `fixture-importer` Compose
service. It runs once at startup and then every
`FA_IMPORT_INTERVAL_SECONDS` (24 hours by default). To run a single import,
use `make import-fixtures`. The importer reads only linked teams with an
`external_provider` of `fa_full_time`, upserts source fixtures idempotently,
and does not delete manually created fixtures. Set `FA_IMPORT_ENABLED=false`
to disable the scheduled service.

## Migrations and tests

Edit SQLAlchemy models in `src/api/models.py`, generate a migration, review the
generated file in `migrations/versions/`, then run `make migrate`. Schema changes
need migrations; hot reload only reloads Python. Tables are created by Alembic,
never by application `create_all()` calls.

Existing databases can apply migration `0002` with `make migrate` or `make restart`.
It converts legacy IDs to UUIDs while preserving records and their relationships;
no reset is needed. Downgrading to `0001` represents club/team UUIDs as text IDs;
it does not recover the original legacy ID strings and removes domain UUIDs.

Tests create a randomly named `final_third_test_*` database, apply real migrations,
and delete that database afterward. They check seed repeatability and preservation,
foreign keys, tenant query scope, public responses, readiness errors, CORS, schema
agreement and migration downgrade/upgrade. The test database user needs CREATEDB
(the local Compose user has it). Run tests only against local development Postgres.

For host-side Python tooling with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
# With the Compose database running (or another local PostgreSQL configured in .env):
uv run pytest
```

Startup ordering follows [Docker's Compose health-check guidance](https://docs.docker.com/compose/how-tos/startup-order/).
Hot reload uses [Uvicorn's reload settings](https://www.uvicorn.org/settings/), and
schema changes use [Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
