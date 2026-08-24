# Productionizing the RAG Service: Multi-user REST API + CI/CD

## Context

The project is currently a single-user CLI/script RAG system over Apple 10-K PDFs:
`main.py` reads questions from stdin, and retrieval is backed by ChromaDB (dense vectors)
+ Redis (parent docstore) + in-memory BM25. There is no API, no auth, no persistent chat
history, and no deployment story beyond a `docker-compose.yml` that only runs Redis.

The goal is to turn this into a **production, multi-user RAG service** with a **REST API**,
**per-user document isolation**, **OAuth login**, and **continuous deployment**, deployed on a
**VPS via Docker Compose** and backed by **Postgres + pgvector** (replacing ChromaDB for vectors
and Redis for the docstore).

Decisions confirmed with the user:
- **Multi-user model:** per-user documents (each user uploads/owns their own PDFs, fully isolated).
- **Auth:** OAuth via Google + GitHub.
- **Deploy:** single VPS + Docker Compose.
- **Store:** Postgres + pgvector (vectors + users + chat + documents in one DB).

## Architecture Overview

```
Browser / API client
        │  HTTPS
        ▼
  Caddy (reverse proxy + TLS) ──────► FastAPI (REST API, OAuth, JWT)
                                          │
                          ┌───────────────┼────────────────┐
                          ▼               ▼                ▼
                     PostgreSQL       Redis (broker)   Celery worker
                     (pgvector)       (job queue)      (async PDF ingestion)
                     users, docs,                       embedding + chunking
                     chunks, sessions
```

- **FastAPI** replaces `main.py` as the entry point. Reuses the existing LangChain pieces
  (`prompt.py`, `model.py`, `data_process.py`, `pipeline.py`) with the retrieval layer re-scoped
  to per-user Postgres.
- **Celery + Redis** for background PDF ingestion (embedding is slow; must not block HTTP).
  Redis is repurposed from "parent docstore" to "job broker + rate-limit store".
- **Postgres + pgvector** becomes the single source of truth for users, documents, chunks
  (with `embedding vector` + `tsvector` columns), sessions, and messages.

## Key Decisions & Rationale

| Decision | Choice | Why |
|----------|--------|-----|
| Web framework | FastAPI + uvicorn | Native async, Pydantic validation, first-class OpenAPI docs |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic | Standard, supports asyncpg + pgvector |
| Dense search | pgvector (`embedding <=> :q`) | Replaces Chroma; same cosine semantics |
| Sparse search | Postgres full-text (`tsvector`/`websearch_to_tsquery`) | Replaces in-memory `rank_bm25`; scales per-user, no per-user index rebuild |
| Hybrid fusion | RRF (Reciprocal Rank Fusion) in Python | Reuses the current `EnsembleRetriever` idea, no vendor lock-in |
| Parent docs | child/parent chunk rows linked by `parent_id` | Mirrors current ParentDocumentRetriever design |
| Auth | `authlib` (OAuth2 code flow) → JWT (`PyJWT`) | Google + GitHub; stateless API auth |
| Async ingestion | Celery + Redis broker | Robust, retryable, standard |
| Config | `pydantic-settings` | Env-var driven, typed, secret-safe |
| TLS / routing | Caddy | Automatic Let's Encrypt HTTPS |
| Deploy | Docker Compose on VPS + GitHub Actions → GHCR | Matches user's choice; simple, auditable |

## Data Model (Postgres, `pgvector` extension enabled)

- **users** — `id`, `oauth_provider`, `oauth_subject`, `email`, `name`, `created_at`.
  Unique on `(oauth_provider, oauth_subject)`.
- **documents** — `id`, `user_id` (FK, indexed), `filename`, `status`
  (`uploaded|processing|ready|failed`), `chunk_count`, `created_at`.
- **chunks** — `id`, `document_id` (FK), `user_id` (denormalized for fast filtering),
  `content`, `embedding vector(384)` (bge-small = 384-d), `tsv tsvector`, `parent_id`
  (nullable FK → chunks, for parent-document links), `chunk_type` (`child|parent`).
- **sessions** — `id`, `user_id`, `title`, `created_at`.
- **messages** — `id`, `session_id`, `role`, `content`, `created_at`.

Indexes: `chunks (user_id)`, `chunks (document_id)`, `chunks (user_id) ON embedding (ivfflat/hnsw)`,
`chunks USING gin(tsv)`.

## API Surface (v1)

- `GET /health` — liveness/readiness.
- `GET /auth/{provider}/login` — redirect to Google/GitHub OAuth (`provider` = `google|github`).
- `GET /auth/{provider}/callback` — OAuth callback → upsert user → issue JWT (redirect with token).
- `POST /auth/refresh` — refresh JWT.
- `GET /me` — current user profile.
- `POST /documents` — multipart PDF upload → enqueue ingestion job.
- `GET /documents` — list user's documents + status.
- `GET /documents/{id}` — document detail.
- `DELETE /documents/{id}` — delete doc + chunks (cascade).
- `POST /chat` — `{session_id?, question}` → answer (+ sources); streams via SSE.
- `GET /sessions` — list sessions.
- `GET /sessions/{id}/messages` — history.

All `/documents`, `/chat`, `/sessions` require a valid JWT; every DB query scoped by `user_id`.

## Implementation Plan

### Phase 0 — Repo hygiene & config
- Split `requirements.txt` into `requirements.in`/pinned, add prod deps
  (fastapi, uvicorn, sqlalchemy, asyncpg, alembic, pgvector, authlib, pyjwt,
  celery, redis, pydantic-settings, python-multipart, httpx).
- Introduce `app/` package; move `src/` modules in (keep `rag` retrieval logic importable).
- Replace `src/config.py` constants with `pydantic-settings` `Settings` (env-driven:
  `DATABASE_URL`, `REDIS_URL`, `DEEPSEEK_API_KEY`, OAuth client IDs/secrets, `JWT_SECRET`).
- Add `.env.example` (no real secrets committed — `.gitignore` already covers `.env`).

### Phase 1 — Database layer
- `docker-compose.yml`: add `postgres` (image `pgvector/pgvector:pg16`) with a named volume.
- SQLAlchemy async engine + models above; Alembic init + initial migration
  (`CREATE EXTENSION vector`, tables, indexes).
- Repo/util module: `init_db`, `get_session` async session dependency.

### Phase 2 — Auth (OAuth + JWT)
- Register Google + GitHub OAuth apps (dev credentials now, prod later).
- `app/auth/` — `authlib` OAuth client, routes, user upsert, JWT encode/decode.
- `get_current_user` FastAPI dependency (parses Bearer token → loads user; 401 on failure).

### Phase 3 — Refactor retrieval to Postgres + per-user scope
- New `app/retrieval.py` (adapts ideas from `src/retriever.py`):
  - Dense: `SELECT ... ORDER BY embedding <=> :q LIMIT :k WHERE user_id = :uid`.
  - Sparse: `... ORDER BY ts_rank(tsv, websearch_to_tsquery('english', :q)) DESC`.
  - Hybrid: fetch top-N from both, fuse with RRF in Python, map children → `parent_id` parents.
- Reuse `src/data_process.py` (`load_pdf`, `get_splitter`) and `src/model.py`
  (`get_embeddings`, `get_llm`) unchanged where possible.
- Reuse `src/prompt.py` (`rag_prompt`) and `format_docs` from `src/pipeline.py`.

### Phase 4 — REST API + async ingestion
- `app/main.py` — FastAPI app, routers, CORS, exception handlers.
- `app/api/` routers: auth, documents, chat, sessions.
- `app/schemas.py` — Pydantic request/response models.
- `app/worker.py` — Celery task: download/read uploaded PDF → chunk (child+parent) →
  embed → insert rows; update `documents.status`.
- Chat endpoint: load user-scoped retriever → build chain (reuse `rag_prompt` + `get_llm`) →
  stream answer + source contexts; persist session/messages.

### Phase 5 — Dockerize
- `Dockerfile` for API (bake embedding model into image at build, or pre-download on start).
- `Dockerfile.worker` for Celery worker (shares base image).
- `docker-compose.prod.yml`: caddy, api, worker, postgres, redis; named volumes for pg data;
  secrets via env file; healthchecks; `restart: unless-stopped`.
- Bake a `models/` layer so the BGE model isn't re-downloaded per deploy.

### Phase 6 — CI/CD (GitHub Actions)
- Keep existing `ci.yaml` test/lint on PRs.
- New `deploy.yaml` on push to `main`:
  1. checkout → run tests (fast, mocked) → build + tag Docker images →
     push to GitHub Container Registry (GHCR).
  2. SSH deploy job (using `appleboy/ssh-action` or a deploy key): `docker compose pull &&
     docker compose up -d --remove-orphans` + run `alembic upgrade head`.
- GitHub Actions secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, OAuth secrets, `DEEPSEEK_API_KEY`,
  `JWT_SECRET`, `DATABASE_URL`.
- Optionally add a `staging` environment first.

### Phase 7 — Observability & hardening
- Structured logging (JSON), request-id middleware, `/health` wired to compose healthchecks.
- Rate limiting (Redis-backed) on `/chat` and `/documents`.
- Postgres backups: `pg_dump` cron container (or `postgres` sidecar with `pg_dump`).
- Error handling: ingestion failures set `documents.status=failed` with retry/backoff in Celery.
- File validation: PDF only, size cap, MIME check before ingestion.

### Phase 8 — Testing & validation
- Unit tests (existing pattern in `tests/`) for retrieval, auth, schemas.
- Integration tests with Testcontainers (Postgres+pgvector, Redis) for ingestion + chat flow.
- E2E: upload a PDF as an OAuth user → poll status → ask a question → assert sourced answer.

## Verification

1. **Local:** `docker compose up` → `GET /health` returns 200; run `alembic upgrade head`.
2. **Auth:** hit `/auth/google/login`, complete OAuth, receive JWT, call `/me`.
3. **Ingestion:** `POST /documents` with a small PDF → Celery logs show chunk/embed →
   `GET /documents` shows `ready` with `chunk_count`.
4. **Chat:** `POST /chat` with a question → streamed answer references correct sources;
   rows appear in `messages`.
5. **Isolation:** create two users, upload different docs, confirm each user's queries only
   retrieve from their own documents (query `chunks` with `user_id` filter).
6. **CD:** push to `main` → GitHub Actions builds/pushes image → VPS pulls and restarts →
   `/health` stays green and a new code change is live.
7. **Tests:** `pytest tests/` (unit + integration) green in CI before deploy.
