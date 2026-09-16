# WatchDog Operator Manual

This manual is written for the owner/operator of WatchDog. It explains what each module does, what it is useful for, what you should feed into it, what you should expect back, and which actions should only be used on systems you own or are explicitly authorized to test.

## 1. Mission of WatchDog

WatchDog is a personal defensive operations console. Its job is to help you:

- understand what information about you or your systems is publicly exposed;
- inspect suspicious messages, links, domains, IPs, files, and account activity;
- collect and preserve evidence in a repeatable way;
- monitor for new mentions of your own identifiers;
- correlate public intelligence feeds;
- test systems you own or are authorized to assess;
- contain, block, deceive, and report malicious activity without attacking third parties;
- keep risky research isolated from your ordinary browser and personal identity.

WatchDog is not designed for unauthorized access, credential theft, malware deployment, destructive activity, denial-of-service, satellite or ground-station compromise, or hack-back.

---

## 2. Core Dashboard Layout

Recommended top-level modules:

1. RECON / OSINT
2. THREAT DECODER
3. INCIDENTS
4. WATCHLISTS
5. NETWORK / IP INTEL
6. AUTHORIZED PEN TEST
7. VULNERABILITIES / CVE
8. DARK WEB / TOR RESEARCH
9. SATELLITE / RF
10. HONEYPOTS / DECEPTION
11. CONTAINMENT / BLOCKING
12. EVIDENCE VAULT
13. EXTERNAL TOOLS
14. PRIVACY / OPSEC

---

## 3. RECON / OSINT

### What it does

Searches public sources for information tied to a name, username, email address, domain, phone number, organization, IP, or other identifier.

### Good uses

- audit your own online footprint;
- find old usernames or exposed contact details;
- locate public documents mentioning you;
- identify reused handles across sites;
- verify whether a suspicious person or domain has a public history;
- gather public context before deciding whether something is a threat.

### Inputs

- full name;
- alias;
- username;
- email address;
- domain;
- phone number;
- exact phrase.

### Outputs

- public mentions;
- social-profile matches;
- indexed documents;
- likely related domains;
- search pivots;
- evidence links.

### Operator rule

Treat OSINT findings as leads, not proof of identity. A username match alone does not prove two accounts belong to the same person.

---

## 4. IP / DOMAIN / DNS / WHOIS / TLS INTELLIGENCE

### IP intelligence

Shows information about the apparent network exit point of an IP address, such as:

- country or region;
- ASN / network owner;
- hosting provider;
- likely data-center, VPN, proxy, mobile, or residential characteristics when a data source supports them.

Important: IP geolocation does not reliably identify a person's physical location. VPNs, Tor exits, proxies, mobile carriers, CGNAT, and compromised infrastructure can all mislead attribution.

### DNS

Resolves records such as:

- A / AAAA;
- MX;
- NS;
- TXT;
- CNAME.

Useful for understanding where a domain is hosted, how mail is configured, and what services may be connected.

### WHOIS / registration data

Useful for:

- registrar identification;
- registration dates;
- name-server history;
- abuse contacts;
- organization data when not privacy-protected.

### TLS / SSL inspection

Useful for:

- certificate issuer;
- validity period;
- subject names;
- certificate chain;
- hostname mismatches;
- expired or misconfigured certificates.

---

## 5. THREAT DECODER

### What it does

You paste a suspicious message, email body, log line, URL, or copied text into WatchDog. It extracts useful indicators without automatically visiting them.

### It should extract

- URLs;
- domains;
- IPv4 / IPv6 addresses;
- email addresses;
- obvious Base64 strings;
- URL-encoded text;
- wallet addresses where supported;
- hashes;
- suspicious file names.

### Safe workflow

1. Paste the suspicious text.
2. Extract indicators locally first.
3. Decode URL encoding and obvious Base64.
4. Do not automatically open unknown links.
5. Hash evidence.
6. Send only indicators to reputation / OSINT sources.
7. Open risky material only in an isolated research environment.

---

## 6. INCIDENT TRIAGE

### Purpose

Turn scattered evidence into one structured incident.

Each incident should include:

- incident ID;
- date/time;
- source;
- summary;
- indicators;
- screenshots/files;
- risk level;
- confidence level;
- actions taken;
- current status;
- evidence hashes.

### Risk scoring

A score should be clearly labeled as heuristic. It can help prioritize incidents, but it should not be treated as proof that a person or source is malicious.

---

## 7. EVIDENCE VAULT

### What it does

Stores copies or references to material relevant to an incident and generates SHA-256 hashes so you can later show that a file has not changed.

### Recommended evidence record

- original file name;
- SHA-256;
- collected timestamp;
- collection source;
- notes;
- related incident;
- screenshot or page copy where lawful and appropriate.

### SHA-256 in plain language

It creates a fixed digital fingerprint. If one byte changes, the hash changes.

---

## 8. WATCHLISTS AND ALERTS

Watchlists should support your own identifiers and assets, such as:

- names and aliases;
- usernames;
- email addresses;
- domains;
- phone numbers;
- company names;
- public wallet addresses you control;
- IPs assigned to your infrastructure.

Alert examples:

- new public mention;
- newly indexed document;
- domain registration resembling yours;
- certificate issued for a suspicious lookalike domain;
- Tor-index mention of one of your identifiers;
- repeated hostile traffic to your own service.

---

## 9. THREAT INTELLIGENCE / REPUTATION

Threat-intel sources help answer questions such as:

- Has this domain been associated with phishing?
- Is this IP commonly used for scanning or abuse?
- Is this file hash known as malware?
- Is this URL already reported as malicious?

Use multiple sources where possible. Reputation systems can be wrong, stale, or biased toward high-volume abuse.

---

## 10. AUTHORIZED PENETRATION TESTING

Only use active testing against systems you own or have explicit permission to test.

### Asset discovery

Finds your systems and services so you know your attack surface.

### Port / service discovery

Identifies exposed network services. This is useful for checking whether your own machine or server exposes something unexpectedly.

### Vulnerability scanning

Looks for known weaknesses, outdated software, weak configurations, or services that map to known CVEs.

### Controlled exploit validation

Used only in a lab or explicitly authorized environment to confirm whether a reported vulnerability is real.

Best practice:

- define the target list first;
- keep a written authorization note;
- rate-limit scans;
- avoid destructive checks;
- record time and tool version;
- stop immediately if the target behaves unexpectedly.

---

## 11. CVE CORRELATION

CVE correlation maps detected software or services to publicly documented vulnerabilities.

Useful output:

- CVE ID;
- severity;
- affected version range;
- public advisory;
- remediation or patch guidance;
- confidence that your detected version is actually affected.

Do not treat a CVE match as proof of exploitability. Version detection can be wrong and many vulnerabilities depend on configuration.

---

## 12. HONEYPOTS / HONEYTOKENS / CANARY LINKS

### Honeypot

A decoy service designed to attract unauthorized interaction so you can observe behavior without exposing a real production service.

### Honeytoken

A fake secret, credential-like value, document, URL, record, or identifier that should never be used legitimately. If someone touches it, that activity is suspicious.

### Canary link

A unique monitored link that alerts when opened.

### Tarpit

A defensive mechanism that deliberately slows obviously abusive automated clients on infrastructure you control.

### Challenge mode

Adds extra verification or friction for suspicious automated traffic.

### Rule

Deception should stay inside systems you own or control. Do not use it to deliver malware, exploit visitors, or retaliate against remote systems.

---

## 13. CONTAINMENT / BLOCKING / REPORTING

Defensive responses can include:

- block IP or ASN on your infrastructure;
- block a user/session;
- revoke tokens or sessions;
- require re-authentication;
- rotate credentials;
- isolate a host;
- disable a compromised account;
- submit abuse reports with evidence;
- preserve logs before cleanup.

WatchDog should favor observe -> verify -> contain -> report over retaliation.

---

## 14. NETWORK MONITORING

Useful defensive monitoring includes:

- authentication failures;
- impossible travel or sudden ASN change;
- repeated probes against your services;
- unusual outbound connections;
- DNS anomalies;
- certificate changes;
- sudden traffic spikes;
- repeated requests to sensitive endpoints.

This works best when WatchDog receives logs from infrastructure you control.

---

## 15. DARK WEB / TOR RESEARCH

Use Tor research for passive investigation, monitoring, and collection of material you are legally entitled to access.

Recommended functions:

- Tor-index searching;
- `.onion` page retrieval through an isolated Tor worker;
- watchlist matching;
- text extraction;
- URL/domain/email/hash/wallet extraction;
- snapshot or page-copy preservation;
- SHA-256 hashing;
- quarantined download collection;
- malware/file scanning before opening;
- evidence linkage into incidents.

Do not use WatchDog to buy illegal goods, access stolen accounts, obtain exploit kits, steal credentials, distribute malware, or facilitate unlawful transactions.

---

## 16. SATELLITE / RF MODULE

Safe, useful capabilities include:

- public TLE / orbital-element tracking;
- satellite position display;
- pass prediction;
- orbit history;
- public satellite imagery;
- public ground-station information;
- legal SDR spectrum observation;
- signal waterfall visualization;
- signal classification;
- interference/anomaly logging;
- correlation with weather, aircraft, maritime, news, and geospatial events.

This module is for observation and analysis. Do not use it to compromise satellites, ground stations, command links, or protected communications.

---

## 17. AIRCRAFT / MARITIME / WEATHER / GEOSPATIAL CORRELATION

Purpose: put multiple public data sources on one timeline and map.

Examples:

- aircraft near an event location;
- vessel movement near a port;
- weather conditions during an incident;
- earthquake or fire activity;
- satellite passes near a time window;
- relevant public news or alerts.

Correlation means 'these things occurred near each other in time or space.' It does not automatically prove causation.

---

## 18. EXTERNAL TOOL INTEGRATION

External security tools should be classified before installation:

### Browser-safe / dashboard adapters

Tools that call public APIs or process local text can often integrate directly.

### Isolated worker tools

Scanners, crawlers, Tor clients, SDR tooling, and anything that opens arbitrary remote content should run on an isolated Linux worker, container, VM, or separate machine.

### Never install blindly

Before integration:

- confirm exact owner/repository;
- read README and license;
- inspect install scripts;
- check dependencies;
- pin a commit or release;
- avoid running unknown code as root;
- never paste production secrets into third-party tools.

---

## 19. PRIVACY / OPSEC MODE

A VPN is useful, but it is not invisibility.

The objective is to reduce correlation between your personal identity, normal browsing, and research activity.

Recommended separation:

1. normal daily device/profile;
2. separate research browser or VM;
3. optional VPN at the host/network layer;
4. Tor Browser or Whonix/Tails for Tor research;
5. no personal logins inside the research environment;
6. separate downloads quarantine;
7. strip metadata before sharing research files;
8. avoid reusing usernames, emails, or browser profiles;
9. do not open downloaded documents directly on your daily-use system;
10. destroy disposable research sessions when finished if they are not needed for evidence.

No stack can make a person completely untrackable. Browser fingerprinting, account correlation, timing, payment records, writing style, file metadata, compromised endpoints, and operational mistakes can all link activity back together.

See DARK_WEB_OPSEC.md for the dedicated research setup.

---

## 20. SIMPLE DAILY WORKFLOW

When something suspicious arrives:

1. Create Incident.
2. Paste the message into Threat Decoder.
3. Extract URLs/domains/IPs/emails.
4. Hash any files.
5. Check reputation and public OSINT.
6. If Tor research is relevant, send only the indicators to the isolated Tor worker.
7. Save findings into the incident.
8. Block or contain only after you have enough confidence.
9. Report abuse where appropriate.
10. Keep the original evidence.

When testing your own system:

1. Add target to Authorized Assets.
2. Confirm ownership/permission.
3. Run discovery.
4. Run service detection.
5. Correlate CVEs.
6. Perform only non-destructive validation.
7. Create remediation tasks.
8. Re-test after fixes.

---

## 21. EXTERNAL PROJECTS CURRENTLY UNDER REVIEW

### simplifaisoul/osiris

OSIRIS is a Next.js / TypeScript global intelligence dashboard with mapping, public intelligence feeds, OSINT tooling, and optional scanner integration. Its UI/data-layer architecture is a good candidate for selective integration or inspiration. Scanner functions should remain isolated and authorization-gated.

### BigBodyCobain/Shadowbroker

Shadowbroker is a Python-based global OSINT platform with aviation, satellite, geospatial, and surveillance-oriented public-data aggregation. Because of its broad data collection and AGPL license, it is better treated as a separate service or isolated integration unless a licensing review says otherwise.

---

## 22. GOLDEN RULES

- Verify before blocking.
- Treat attribution as probabilistic.
- Separate passive research from active testing.
- Keep active testing restricted to authorized targets.
- Keep Tor and arbitrary-content retrieval isolated.
- Hash evidence before altering it.
- Never run unknown third-party security code with production secrets.
- Prefer containment and reporting over retaliation.
- Keep research identity separate from personal identity.
