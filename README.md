# Book AI — reading companion SaaS

A Django + DRF backend that ingests books (PDF, EPUB, DOCX, TXT), explains
passages, answers questions about the text, generates quizzes, and tracks
reading progress — with Stripe subscriptions gating usage. Built to deploy
on Render.

## How it works

1. A user uploads a book. The file is saved and a Celery task is queued
   (`ingestion.tasks.process_book`) so the upload request returns instantly.
2. The worker parses the file (`ingestion/parsers.py`), splits it into
   chapters, then splits each chapter into overlapping ~600-token chunks
   (`ingestion/chunking.py`).
3. Each chunk is embedded (`ai/embeddings.py`, OpenAI) and stored in
   Postgres via `pgvector`.
4. "Explain this", "answer my question", and "quiz me" all go through
   `ai/rag.py`: the query is embedded, the closest chunks are retrieved by
   cosine similarity, and Claude generates a grounded response from just
   those excerpts — not from memory, and not by reproducing long verbatim
   passages (see the prompts in `ai/prompts.py`).
5. Reading position and percent complete are tracked per user per book
   (`library.models.Progress`).
6. Stripe Checkout handles subscriptions; a webhook keeps `Profile.plan`
   and usage limits in sync (`billing/`).

## Local setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, REDIS_URL, API keys

# Postgres needs the pgvector extension available before migrating —
# either install the pgvector extension package on your Postgres server,
# or use a Postgres image that already bundles it (e.g. pgvector/pgvector
# on Docker Hub). The first migration runs CREATE EXTENSION for you.

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

In a second terminal, run the worker (needed for book processing):

```bash
celery -A config worker -l info
```

You'll need Redis running locally too (`redis-server`, or `docker run -p 6379:6379 redis`).

## Key environment variables (see `.env.example` for the full list)

- `DATABASE_URL`, `REDIS_URL` — infra
- `OPENAI_API_KEY` — used only for embeddings (Anthropic has no embeddings endpoint yet)
- `ANTHROPIC_API_KEY` — used for explain/answer/quiz generation
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_PRO` — billing

## API surface (all under `/api/`, token auth)

- `POST /api/auth/token/` — get an auth token (username + password)
- `POST /api/books/` — upload a book (`multipart/form-data`, field `file`)
- `GET /api/books/` — list your books, with `status` (pending/processing/ready/failed)
- `GET /api/books/{id}/chapters/` — chapter list once processed
- `POST /api/books/{id}/explain/` — `{"chunk_id": N}` → explanation
- `POST /api/books/{id}/ask/` — `{"question": "..."}` → grounded answer
- `POST /api/books/{id}/quiz/` — `{"topic": "optional"}` → generated quiz
- `POST /api/progress/update-for-book/` — `{"book": id, "last_chunk_order": N}`
- `GET /api/questions/?book={id}` — Q&A history for a book

Billing under `/billing/`: `POST /billing/checkout/`, `POST /billing/portal/`, `POST /billing/webhook/` (point your Stripe webhook here).

## Deploying to Render

`render.yaml` defines the full stack: a web service, a Celery worker, managed
Postgres, and managed Redis.

1. Push this repo to GitHub.
2. In Render, choose "New > Blueprint" and point it at the repo — it reads
   `render.yaml` and provisions everything.
3. On the Postgres instance, enable the `vector` extension once if it isn't
   auto-enabled by the first migration: connect via `psql` and run
   `CREATE EXTENSION IF NOT EXISTS vector;`
4. Fill in the `sync: false` environment variables in the Render dashboard
   (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, Stripe keys) — these aren't
   committed to the repo.
5. Add file storage: Render's disks aren't reliable for user uploads across
   deploys, so set `USE_S3=True` and point it at Cloudflare R2, Backblaze B2,
   or AWS S3 (any S3-compatible provider works via `django-storages`).
6. Point your Stripe webhook at `https://<your-app>.onrender.com/billing/webhook/`.

## What's deliberately NOT built here (next steps)

- **Frontend.** This is an API-only backend. Pair it with a React/Next.js
  app or server-rendered Django templates — the API is designed to support
  either.
- **PDF chapter detection.** PDFs are ingested as one long chapter today;
  a heading-detection heuristic (font-size jumps, "Chapter N" regex) would
  improve chapter-level navigation without touching the chunking/embedding
  pipeline.
- **Rate limiting at the API layer** beyond the plan-based counters (add
  `django-ratelimit` or DRF throttling if you're worried about abuse).
- **Monthly usage reset scheduling.** `ingestion.tasks.reset_usage_counters`
  exists but needs to be wired to Celery beat with a monthly schedule.
- **Copyright safeguards beyond scoping uploads per-user.** Read the
  caution in the project notes: don't add features that return long
  verbatim passages, and keep your ToS explicit that users must have rights
  to what they upload.
