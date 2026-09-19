# WatchDog Next.js + FastAPI migration

This branch migrates WatchDog toward a Next.js/React frontend with Python FastAPI as the application backend.

## Non-mockup rule

A feature is not added to the new frontend unless it has a real FastAPI endpoint or a real browser API behind it. Placeholder buttons and staged result cards are intentionally excluded.

## Current migrated functions

- Python session login
- OpenAI assistant from Python only
- Evidence text hashing and indicator extraction
- Public IP intelligence
- NHTSA VIN decoding
- OpenStreetMap/Nominatim place search
- Existing Python public OSINT engine
- Existing Python bounded public site crawler
- Authorized bounded TCP port probe
- Authorized web response-security check
- Browser Web Bluetooth device chooser
- Browser Web NFC reader

## Security model

The browser never receives OPENAI_API_KEY or WATCHDOG_WORKER_API_KEY. The user signs in to the Python API with WATCHDOG_ADMIN_PASSWORD. Python issues a short-lived HMAC-signed session token. All application tools except `/health` and `/v1/auth/login` require that session.

Active network checks still require a separate per-action authorization confirmation and reject private, loopback, link-local, reserved and non-global targets.

## Local run

Backend:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
export WATCHDOG_ADMIN_PASSWORD='change-me'
export WATCHDOG_SESSION_SECRET='replace-with-a-long-random-secret'
export WATCHDOG_ALLOWED_ORIGINS='http://localhost:3000'
uvicorn backend.app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

## Deployment shape

- Next.js frontend: Vercel or Netlify
- Python FastAPI: Render, Railway, Fly.io, or another container host
- OPENAI_API_KEY: Python backend only
- `NEXT_PUBLIC_WATCHDOG_API_URL`: public HTTPS URL of the Python backend
- `WATCHDOG_ALLOWED_ORIGINS`: exact deployed frontend origin

The legacy HTML/Node application remains untouched on `main` while this branch is tested.
