# Deploy on Vercel (serverless)

**Two Vercel projects from this one repo, one shared database.** Public site and
admin back office live on separate domains; each is same-origin (SPA + its own
`/api` on the same host), so every login cookie stays first-party — **no CORS,
no `SameSite=None`**. They differ only by two flags (below) and their env vars.

```
surfwinddata.com (public project)          kjellmittelsdorf.de (admin project)
 ├── /            → public SPA               ├── /            → redirects to /admin
 │                  (NO admin code)          ├── /admin       → back-office SPA + login
 └── /api/*       → FastAPI                  └── /api/*       → FastAPI
       (public + community routes only)            (full: + /auth + /admin*)
                    \                               /
                     \____ same Neon DB + Upstash + Blob ____/
```

The split is driven by two flags:

| Flag | Public project | Admin project | Effect |
|---|---|---|---|
| `VITE_INCLUDE_ADMIN` (build) | *unset* | `true` | Admin UI compiled into the bundle only when `true`; the public build ships zero admin code (no admin chunk, no `/admin`/`/auth` strings). |
| `ENABLE_ADMIN_API` (runtime) | `false` | `true` | Public function drops the `/auth` + `/admin*` routers entirely. The default is fail-closed (`false`). |

Both projects: **Root Directory = repo root** (so the full-stack `vercel.json`
bundles `api/index.py`), same build command. Local `npm run dev` always includes
admin at `/admin` and keeps the public landing at `/`.

Because each SPA and its `/api` share one origin, the login cookie stays same-site
(`SameSite=Lax` + `Secure`) and there is **no CORS**.

> **Honesty note.** Vercel can't run your Postgres/Redis/background jobs — those
> move to managed services, and the climatology batch runs **offline** (below).
> The repo is already prepared for this (see the changes referenced per step),
> but the Vercel-specific bits (function bundling, the 250 MB size limit on Linux,
> the `/api` path handling) can only be fully confirmed on a real deploy. If
> something 404s or the build is too big, see **Troubleshooting**.

---

## What's already done in the repo
- `api/index.py` — serverless ASGI entry (strips the `/api` prefix so FastAPI keeps its root routes).
- `vercel.json` — builds the SPA with `VITE_API_URL=/api`, routes `/api/*` to the function, SPA fallback for the rest.
- `api/requirements.txt` — **slim** function deps (no `pyarrow`/`uvicorn`/`alembic`/`pytest`) to stay under Vercel's 250 MB limit. `rawfile.py` now imports `pyarrow` lazily, so the request path never loads it (verified).
- `media_backend=blob` support (`app/media/storage.py`) — uploads to Vercel Blob and stores absolute URLs; the local disk path is unchanged for dev/VPS.
- Vercel is detected automatically and uses SQLAlchemy `NullPool` (the
  `DB_SERVERLESS=true` flag remains available for other serverless hosts).
- App start no longer creates a media dir / mounts StaticFiles in blob mode (won't crash on the read-only serverless FS).

---

## Step 1 — Neon (Postgres + PostGIS)
1. Create a project at <https://neon.tech>. Note **two** connection strings:
   - **Direct** (for migrations): `...neon.tech/neondb?sslmode=require`
   - **Pooled** (for the app): host ends in `-pooler`, `...-pooler.neon.tech/...`
2. Convert them to the SQLAlchemy/psycopg form by prefixing the scheme:
   `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`
3. PostGIS is enabled by the first migration (`CREATE EXTENSION postgis`). If Neon
   requires enabling it first, run once in the Neon SQL editor: `CREATE EXTENSION IF NOT EXISTS postgis;`

## Step 2 — Upstash Redis
1. Create a database at <https://upstash.com> → copy the **`rediss://…`** URL.
   (Redis is a non-critical cache; `/health` reports `degraded`, not down, if it's off.)

## Step 3 — Vercel Blob
1. In the Vercel project → **Storage → Create → Blob**, connect it to the project.
2. Vercel auto-adds the **`BLOB_READ_WRITE_TOKEN`** env var — you don't set it by hand.

## Step 4 — migrate + seed + climatology (OFFLINE, from your machine)
Run these locally against Neon **before/at first deploy** — they don't run on Vercel:
```bash
# use the DIRECT (non-pooled) Neon URL here
export DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST/neondb?sslmode=require"

python -m alembic upgrade head          # schema + PostGIS
python -m app.seed.seed                 # regions + spots (if you seed)
python -m app.era5.batch --status all   # climatology (long-running; Vercel can't do this)
python -m scripts.verify_content        # red/green check
```
Re-run `app.era5.batch` from your machine whenever you add spots (it's idempotent).

## Step 5 — Vercel projects (two)
Import the `surfwinddata` repo **twice** — once per project. Both keep **Root
Directory = repo root** (the included `vercel.json` drives the build).

**Shared env vars** (set on *both* projects, identical values — same DB/cache/blob):

| Key | Value |
|---|---|
| `DATABASE_URL` | Neon **pooled** URL (`postgresql+psycopg://…-pooler…?sslmode=require`) |
| `DB_SERVERLESS` | `true` |
| `REDIS_URL` | Upstash `rediss://…` |
| `MEDIA_BACKEND` | `blob` |
| `BLOB_READ_WRITE_TOKEN` | (auto-added by each project's Blob store — leave it) |
| `ERA5_AUTOPROCESS` | `false` (no background threads on serverless) |
| `API_DEBUG` | `false` |
| `APP_ENV` | `production` |
| `COOKIE_SECURE` | `true` |
| `JWT_SECRET` | independent `openssl rand -base64 48` secret per project |

**Public project** (`surfwinddata.com`) — add only:

| Key | Value |
|---|---|
| `ENABLE_ADMIN_API` | `false` (drops `/auth` + `/admin*`) |
| `DEPLOYMENT_MODE` | `public` |

*(no `VITE_INCLUDE_ADMIN` or `ADMIN_BOOTSTRAP_*` — the public build has no admin. `JWT_SECRET` is still required because public accounts use signed sessions.)*

**Admin project** (`kjellmittelsdorf.de`) — add:

| Key | Value |
|---|---|
| `VITE_INCLUDE_ADMIN` | `true` (compiles the admin UI into the build) |
| `DEPLOYMENT_MODE` | `admin` |
| `ENABLE_ADMIN_API` | `true` |
| `ADMIN_BOOTSTRAP_EMAIL` | your admin email |
| `ADMIN_BOOTSTRAP_PASSWORD` | a strong password (change after first login) |
| `COOKIE_SECURE` | `true` |
| `TAKEDOWN_CONTACT_EMAIL` | e.g. `abuse@kjellmittelsdorf.de` |

The admin build intentionally contains only dashboard routes. Legal operator
variables are required by `build:release` only for the separate public project.

Production configuration is validated at process start; unsafe combinations do
not boot.

3. **Deploy both.** Point `surfwinddata.com` at the public project and
   `kjellmittelsdorf.de` at the admin project (Settings → Domains).

## Step 6 — domain
Project → **Settings → Domains** → add `kjellmittelsdorf.de` → set the DNS records
Vercel shows you.

After deploy: `https://kjellmittelsdorf.de` = site, `…/admin` = dashboard (login
with the bootstrap admin).

---

## Troubleshooting
- **API calls 404 after deploy** → the function may already receive the path
  *without* `/api`. In `api/index.py` remove the `/api` strip (or adjust `_PREFIX`).
- **Build too big / 250 MB** → check the function bundle size in the build log.
  The heaviest remaining deps are `numpy`, `psycopg[binary]`, `pillow`, `shapely`.
  If over the limit, drop `pillow-avif-plugin` (falls back to WebP) or trim further.
- **`prepared statement "…" already exists`** (Neon pooled + psycopg) → transaction
  pooling doesn't like prepared statements. Add to `app/db/session.py`
  `connect_args={"prepare_threshold": None}` on the engine (only in serverless mode).
- **Image upload fails / bad URL** → the Blob branch in `app/media/storage.py`
  is best-effort and unverified against a live token; confirm the PUT response and
  the returned `url`, and adjust `_blob_put` to Vercel Blob's current REST shape.
- **Cold starts** slow on first hit — expected for a serverless FastAPI; fine for
  an admin tool + cached live data (Upstash).
- **`/health` reports `schema: outdated`** → code and Neon revision do not match.
  Production migrations run automatically only after Vercel reports a successful
  production deployment; the workflow can also be started manually. It uses the
  minimal `requirements-migrate.txt`, so large runtime/data packages do not delay
  schema readiness.

## What still runs off-Vercel
- The **ERA5 climatology batch** (`python -m app.era5.batch`) — long-running, needs
  `pyarrow`; run it from your machine/CI against Neon. Live/forecast (short,
  Upstash-cached) runs fine in the function.
