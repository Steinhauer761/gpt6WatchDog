# WatchDog Dark Web / Tor Research & OPSEC Guide

This guide is for lawful defensive research, monitoring your own identifiers/assets, incident investigation, and collecting publicly accessible threat intelligence. It is not a guide for unauthorized access, stolen accounts, malware distribution, illegal transactions, or evading lawful investigation.

## 1. What a VPN actually does

A VPN mainly changes which network sees your direct Internet traffic and which public IP websites see. It does not make you anonymous by itself.

A VPN does not automatically hide:

- browser fingerprint;
- cookies;
- logins;
- reused usernames;
- account history;
- device compromise;
- payment identity;
- document metadata;
- writing-style correlation;
- timing correlation;
- mistakes made outside the VPN.

Treat it as one transport layer, not an invisibility switch.

---

## 2. Better goal: reduce linkability

The practical objective is compartmentalization: make it difficult to connect research activity to your normal identity by keeping identities, browsers, files, networks, and sessions separate.

Recommended research stack:

Normal host/device
-> optional VPN
-> isolated research VM or dedicated machine
-> Tor Browser / Whonix / Tails when Tor is needed
-> isolated downloads/quarantine
-> evidence export only after review

Do not log into personal Google, Facebook, GitHub, email, banking, or social accounts inside the research compartment.

---

## 3. Recommended environments

### Tor Browser

Good for routine `.onion` browsing and passive research.

Advantages:

- routes browser traffic through Tor;
- standardizes many browser settings to reduce fingerprint uniqueness;
- isolates site data better than a normal browser with a Tor proxy extension.

Operator rule: do not install extra browser extensions. They can make your browser more unique.

### Tails

A live operating system designed for temporary private sessions.

Useful when:

- you want a disposable research environment;
- you do not need persistent local state;
- you want traffic routed through Tor by design.

### Whonix

Uses separate Gateway and Workstation virtual machines so the application environment does not directly know the real network interface.

Useful when:

- you want a persistent Tor research workstation;
- you want stronger network separation than a normal browser profile;
- you need repeatable research tools inside a controlled VM.

---

## 4. VPN + Tor

There are different ways to combine them, and adding layers does not automatically make things safer.

For most WatchDog research, keep it simple:

- use a reputable VPN if you already trust it and want your ISP/local network to see only VPN traffic;
- run Tor Browser or Whonix inside the research environment;
- do not manually alter Tor routing unless you have a specific reason and understand the failure modes.

WatchDog should report the current path as 'VPN present', 'Tor present', or 'direct', but should never claim 'anonymous'.

---

## 5. Research identity separation

Create a research identity compartment that is not reused elsewhere.

Do not reuse:

- personal email addresses;
- usual usernames;
- profile photos;
- personal recovery emails/phones;
- distinctive bios;
- passwords;
- browser sync accounts.

If an investigation requires authentication to a service you legitimately use, keep that authenticated work in a separate compartment from anonymous browsing so the identities do not accidentally mix.

---

## 6. Browser fingerprinting

Sites can combine many details to recognize a browser even when IP addresses change.

Examples:

- screen size;
- fonts;
- browser version;
- language;
- timezone;
- canvas/WebGL behavior;
- hardware hints;
- extension list;
- cookies/local storage.

Tor Browser reduces fingerprint uniqueness by making many users look similar. Customizing it heavily can defeat that benefit.

---

## 7. DNS and WebRTC leak awareness

A privacy dashboard can test whether normal-browser traffic is exposing unexpected DNS resolvers or local/public IP information.

For Tor Browser, do not bolt on random leak-prevention extensions. Use Tor Browser's defaults and keep it updated.

For ordinary VPN browsing, verify:

- VPN kill switch if available;
- DNS queries use the intended path;
- WebRTC does not expose unexpected addresses;
- IPv6 is handled correctly by the VPN.

WatchDog can expose these as health checks rather than claiming a perfect anonymity score.

---

## 8. Dark-web search workflow

Safe workflow:

1. Start isolated research environment.
2. Connect using your planned network path.
3. Launch Tor Browser / Tor worker.
4. Search known Tor indexes or trusted threat-intel collections.
5. Search only the identifiers relevant to the investigation.
6. Record page title, onion address, collection time, and context.
7. Extract indicators.
8. Hash saved evidence.
9. Do not log into unrelated services.
10. End or destroy the disposable session when finished.

---

## 9. WatchDog Tor worker

The WatchDog architecture should keep Tor retrieval off the public Vercel frontend.

Recommended design:

WatchDog UI
-> authenticated job request
-> isolated Linux worker
-> Tor SOCKS proxy
-> retrieval/extraction
-> malware/file triage
-> sanitized findings
-> WatchDog evidence store

Worker controls should include:

- outbound traffic restricted to Tor when operating in Tor mode;
- no access to production secrets;
- no access to your normal browser cookies;
- strict download size limits;
- MIME/type checks;
- file hashing;
- optional antivirus/YARA scanning;
- timeouts;
- rate limits;
- automatic cleanup of temporary files.

---

## 10. Pulling resources from Tor safely

When you intentionally save a file or page for research:

### Pages

Prefer saving:

- sanitized HTML/text;
- screenshot/PDF snapshot;
- extracted indicators;
- SHA-256 hash;
- source onion address;
- timestamp.

### Downloads

Treat every downloaded file as hostile until proven otherwise.

Do not:

- double-click it on your daily-use machine;
- enable macros;
- run executables;
- allow a PDF/document viewer unrestricted network access;
- upload sensitive evidence to public malware-analysis services without considering confidentiality.

Recommended flow:

Tor worker downloads file
-> calculate SHA-256
-> identify real file type
-> static scan
-> quarantine
-> inspect in disposable offline/sandbox VM if needed
-> export only safe derived evidence

Documents can contain remote images, active content, macros, links, or exploits. Opening a document outside the isolated environment can reveal your normal IP or expose your system.

---

## 11. Metadata

Before sharing screenshots, photos, PDFs, documents, archives, or media created during research, inspect metadata.

Metadata can include:

- author name;
- software name;
- device model;
- GPS coordinates;
- timestamps;
- original file paths;
- embedded usernames.

WatchDog should provide a 'metadata review' stage before evidence export.

Do not alter the original evidence file itself. Preserve the original hash and make a separate sanitized copy for sharing.

---

## 12. Active content

For Tor research, prefer static pages and text extraction.

JavaScript and other active content can increase exposure and tracking risk. Tor Browser's security level can be raised for riskier sites, but some sites will break.

The WatchDog worker should never execute arbitrary downloaded binaries or scripts simply because a page linked them.

---

## 13. Correlation risks

Even with VPN + Tor, activity can become linkable through behavior.

Common mistakes:

- logging into a personal account;
- using the same alias everywhere;
- copying a unique profile description;
- opening a downloaded document normally;
- posting at distinctive times;
- revealing personal facts;
- reusing a cryptocurrency/payment identity;
- uploading the same image with identifying metadata;
- switching between research and personal accounts in one browser.

The best privacy improvement is disciplined separation, not stacking endless network tools.

---

## 14. WatchDog Privacy / OPSEC dashboard

Suggested indicators:

- Research environment: NORMAL / ISOLATED
- Tor route: ON / OFF
- VPN route: ON / OFF / UNKNOWN
- DNS path: EXPECTED / WARNING
- WebRTC exposure check: PASS / REVIEW
- Browser compartment: RESEARCH / PERSONAL
- Personal accounts detected: YES / NO
- Download quarantine: ACTIVE / INACTIVE
- Evidence hashing: ACTIVE
- Metadata review required: YES / NO

Never show a misleading '100% anonymous' badge.

---

## 15. Research modes

### Mode A - Public Web OSINT

Use normal isolated research browser. VPN optional.

### Mode B - Tor Passive Research

Use Tor Browser or WatchDog Tor worker. Do not perform active probing against onion services.

### Mode C - Evidence Collection

Capture page/text/file, hash immediately, quarantine files, preserve source and timestamp.

### Mode D - Authorized Testing

Use a separate lab/authorized-testing worker. Do not mix penetration-testing traffic with anonymous Tor research.

---

## 16. Why pen-test traffic and Tor research should be separated

Do not use Tor as a disguise for active testing.

For an authorized penetration test, you want:

- a documented source IP;
- clear authorization;
- predictable logs;
- reliable network behavior;
- an audit trail.

For passive Tor research, you want isolation and minimum interaction.

These are different missions and should use different workers.

---

## 17. Satellite / RF privacy note

Satellite and SDR research can be passive, but radio activity can become regulated depending on frequency, jurisdiction, encryption, transmission, and equipment.

WatchDog should separate:

- public orbital data and imagery;
- receive-only SDR observation where lawful;
- active transmission/testing on equipment you own and frequencies you are authorized to use.

Do not use the privacy stack to conceal unauthorized interference, access, or commands directed at satellites or ground infrastructure.

---

## 18. End-of-session checklist

Before leaving a Tor research session:

- save only necessary evidence;
- hash originals;
- record timestamps/sources;
- move suspicious downloads to quarantine;
- close sites;
- clear or destroy disposable workspace as planned;
- do not move raw hostile files into your normal Downloads folder;
- review exported files for metadata;
- update the incident record.

---

## 19. Practical rule of thumb

VPN = hides your direct destination traffic from the local network/ISP and changes your visible public IP, depending on provider trust.

Tor = routes traffic through multiple relays and is designed to reduce source/destination linkage.

Isolated VM/Tails/Whonix = reduces the chance that research activity touches your ordinary identity or host environment.

Compartmentalization = the part most people forget, and often the part that matters most.

No single layer makes you invisible.
