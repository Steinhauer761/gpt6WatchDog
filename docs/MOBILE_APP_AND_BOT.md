# WatchDog Mobile App + Bot Guide

## Android install model

WatchDog is packaged first as a Progressive Web App (PWA). On Android it can be installed from Chrome and opens in its own standalone window with its own launcher name and icon.

Current neutral launcher identity:

- App name: `Field Tools`
- Icon: `app-icon.svg`

These are cosmetic launcher settings only. They do not make the app invisible to Android, network logs, device management, backups, or account-level monitoring. Do not impersonate another real app.

### Install on Android

1. Open the hosted WatchDog `app.html` URL in Chrome.
2. Wait for the WatchDog console to load.
3. Open Chrome's menu.
4. Choose **Install app** or **Add to Home screen**.
5. Confirm the install.
6. Launch `Field Tools` from the Android launcher.

The PWA service worker caches only the application shell. Dynamic OSINT results, worker responses, credentials and secret tokens must not be added to the offline cache.

## Changing the launcher identity

Edit `manifest.json`:

- `name`
- `short_name`
- `theme_color`
- `background_color`

Replace `app-icon.svg` with another icon you own. Keep the same filename to avoid touching the manifest.

## Architecture

Phone PWA
-> authenticated HTTPS worker API
-> isolated Linux security worker(s)
-> tool adapters / passive collectors / authorized scanners

Telegram bot
-> passive triage + alerts + links back to WatchDog
-> no active scan launch from chat

## Linux worker

The Linux worker is where heavyweight tools belong. Do not run Nmap, Nuclei, ZAP, Kismet, Tor crawlers, SDR decoders or honeypot services inside the static phone frontend.

Recommended worker isolation:

- dedicated VPS, mini-PC or VM;
- non-root containers where possible;
- separate containers for Tor, active authorized testing, RF/SDR and honeypots;
- outbound allowlists for sensitive jobs;
- per-job timeouts and concurrency limits;
- audit log containing target, tool, operator confirmation, start time, end time and result hash;
- API key between WatchDog and the worker;
- never expose tool shells directly to the public Internet.

## Telegram companion bot

`worker/watchdog_bot.py` is the first companion bot scaffold.

Required environment variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_ID`
- `WATCHDOG_BASE_URL` (optional until the console is hosted)

Supported first-pass commands:

- `/status` — confirm bot/worker status;
- `/triage <text>` — passive heuristic triage and SHA-256 hashing;
- `/search <identifier>` — create/open a public OSINT search in WatchDog.

Active penetration-test jobs are intentionally not available from chat commands. Those remain behind the dashboard authorization controls.

## Notifications to add next

The bot can later notify you when:

- a watchlist finds a new public mention;
- a canary token fires;
- a honeypot receives interaction;
- an owned server triggers Suricata/CrowdSec rules;
- a scheduled authorized scan finishes;
- a new high-severity CVE affects an asset in your inventory;
- a Tor-watch job finds a new match for one of your own monitored identifiers;
- the worker goes offline.

## Deployment note

Production frontend branch: `feature/security-toolbox-v1`. The Vercel Production environment should track this branch while the toolbox is being validated before merge to `main`.
