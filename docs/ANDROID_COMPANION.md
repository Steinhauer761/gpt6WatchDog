# WatchDog Android Companion

The Android companion is a real phone-side client for the WatchDog Python backend. It is designed to keep the interface simple while leaving the technical work in the backend.

## What it does

### Connect + pair
Enter the HTTPS address of the WatchDog FastAPI backend and the WatchDog console password once. The app uses the normal admin login only to request a limited `watchdog-mobile` token. The console password is not stored. The mobile token and backend URL are encrypted using Android Keystore.

### Share or select text to scan
From Messages, a browser, or a social app, use **Share → WatchDog Companion**. You can also select text and choose WatchDog from Android's Process Text menu. The app sends only the text you explicitly chose to the mobile triage endpoint and shows a plain-language result first.

### Scam score + local blocking
If you include a phone number, the companion uses the same WatchDog scam scoring engine as the web console. When **Auto-block 8–10** is enabled, a displayed number that scores 8–10 is stored in the phone's local WatchDog block list.

After you grant WatchDog Android's **Call Screening** role, future incoming calls from a locally blocked displayed number are rejected before ringing. The number remains reviewable and can be removed from the block list.

Caller ID can be spoofed. A block protects the phone from the displayed number; it does not claim the subscriber who owns that number was the scammer.

### What it does not do
The companion does not block IP addresses and therefore does not interfere with normal web, Tor, or WatchDog research traffic. It does not request broad SMS-history access, contacts, location, microphone, camera, or call-log permissions.

Automatic SMS-body monitoring is intentionally not included in this first companion build. Android/Google Play treats SMS access as highly sensitive. For now, sharing or selecting a suspicious message is the explicit scan action. Call screening itself is automatic once the user grants the Call Screening role.

## Backend routes

- `POST /v1/mobile/pair` — admin-authenticated pairing that issues a limited mobile token.
- `POST /v1/mobile/triage/text` — mobile-token text/evidence triage.
- `POST /v1/mobile/scam/triage` — mobile-token scam reportability scoring.

A mobile token cannot call admin-only tools such as IP intelligence, research crawling, or network probes.

## Build

The Android project lives under `/android`, uses Java 17, Android Gradle Plugin 9.2.0, Gradle 9.4.1, `compileSdk 37`, `targetSdk 37`, and `minSdk 29`.

CI builds a debug APK with:

```bash
gradle -p android :app:assembleDebug
```
