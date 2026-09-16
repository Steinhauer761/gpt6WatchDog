# WatchDog Security Worker

This directory is reserved for tools that should not execute inside the browser or Vercel frontend.

## Why a separate worker

Many OSINT and security projects require Python, system packages, headless browsers, DNS/network access, Tor, or long-running jobs. Those belong in an isolated Linux worker/container with strict limits rather than the public frontend.

## Integration rules

1. Pin every third-party project to an exact upstream `owner/repo` and reviewed commit/tag.
2. Record its license and install requirements before enabling it.
3. Run tools with a non-root user and read-only filesystem where practical.
4. Apply hard execution timeouts, low concurrency, rate limits, and output-size limits.
5. Never pass platform secrets or production credentials into a third-party tool unless specifically required and reviewed.
6. Accept only explicit indicators or owned/authorized targets.
7. Store the command, target, start/end timestamps, tool version and result hash for each run.
8. Do not implement hack-back, retaliation, credential theft, persistence or destructive actions against third-party systems.

## Planned API shape

The frontend should call a WatchDog-owned API rather than invoking tools directly:

- `POST /jobs` — create an authorized enrichment job
- `GET /jobs/:id` — retrieve status and sanitized findings
- `POST /incidents` — preserve incident metadata and evidence hashes
- `POST /watchlists` — register user-owned identifiers for monitoring

Each job should include:

```json
{
  "tool_id": "username-osint",
  "target_type": "username",
  "target": "example-handle",
  "authorization_scope": "self-audit",
  "case_id": "optional-case-id"
}
```

## Next step

Verify the exact GitHub URLs of the third-party repositories selected for WatchDog. After review, add one adapter at a time with a pinned version and a test fixture before enabling it in the UI.
