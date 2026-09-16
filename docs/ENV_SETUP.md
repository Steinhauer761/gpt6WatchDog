# WatchDog configuration

The WatchDog web app uses Vercel project `gpt6-watch-dog` and the Docker/Python
worker uses a separate Render service. The browser never receives either key.

## AI assistant on Vercel

In the Vercel project's **Settings → Environment Variables**, set
`OPENAI_API_KEY` for Production to a new OpenAI **project API key**. The route
`/api/assistant` calls `POST /v1/responses`, so a restricted key needs
**Responses: Write**. A read-only key will fail. Set `OPENAI_MODEL` only if you
want to override the default in `api/assistant.js`. Add the same settings to
Preview separately if you use preview deployments. Redeploy after updating
environment variables, then test the assistant with a short message.

The old key was committed to this public repository earlier. Revoke it in the
OpenAI Platform and do not reuse it or paste a new key into GitHub files,
frontend code, chat, or a screenshot. ChatGPT subscriptions and OpenAI API
billing are separate; check the API project's billing and spending limit.

## Worker bridge

Vercel's `WATCHDOG_WORKER_API_KEY` must match the **different**
`WATCHDOG_WORKER_API_KEY` on Render. `WATCHDOG_WORKER_URL` points to
`https://gpt6watchdog-2.onrender.com` unless the worker moves. The worker can
be checked without a key through `GET /api/worker?action=health`; protected
tools can be checked through `GET /api/worker?action=capabilities`.

Only rotate the worker key if it has been exposed or the bridge fails.
`worker/.env.example` documents the worker-only settings. The legacy manual
GitHub Actions orchestrator uses its own `OPENAI_API_KEY` repository secret;
that secret does not configure the Vercel assistant.
