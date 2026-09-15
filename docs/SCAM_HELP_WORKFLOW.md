# WatchDog Scam / Fake Account Assistance Workflow

Use this workflow when helping yourself or another person investigate a suspected scam, impersonation account, fake seller, phishing attempt, or suspicious public profile.

## 1. Get Permission and Define the Case

If you are helping another person, make sure they want your help and understand what you are collecting.

Record:

- platform or service;
- public username / profile URL;
- suspicious email, domain, URL or phone number if voluntarily provided by the victim;
- what the account claimed;
- what was requested (money, login, install, transfer, gift card, crypto, documents, etc.);
- dates and approximate times;
- whether money or credentials were already sent.

Do not collect unrelated private information about the suspected person.

## 2. Preserve Before Investigating

Before contacting, blocking, reporting, or changing anything:

- save the exact public profile URL;
- capture screenshots with visible dates/times when possible;
- export or preserve original messages;
- preserve full email headers when email is involved;
- save transaction IDs and receipts;
- save suspicious URLs without opening them unnecessarily;
- hash evidence files with SHA-256.

WatchDog's Scam Case Builder hashes selected files locally in the browser.

## 3. Separate Observation From Interpretation

Good observation:

> The profile requested a $300 payment by gift card at 14:22 and linked to example-domain.test.

Assessment:

> The payment method and off-platform link are consistent with common scam patterns.

Avoid statements such as "this person is definitely a criminal" unless that fact has been established by an appropriate authority.

## 4. Public-Source Investigation

Safe pivots include:

- exact username searches;
- public social-media profiles;
- reused usernames via Sherlock;
- publicly indexed documents;
- public GitHub references;
- domain registration / RDAP / DNS / certificate data;
- public IP / ASN context from evidence already received;
- public threat-intelligence and reputation sources;
- reverse-image searches performed through reputable services;
- public Tor-index references;
- archived public pages.

Treat matches as leads. The same username or profile photo can be reused by unrelated people.

## 5. Infrastructure Checks

For a suspicious domain, email or link, WatchDog may passively inspect:

- domain age / registration metadata when public;
- DNS records;
- certificate transparency records;
- hosting provider / ASN;
- URL reputation;
- known malware / phishing indicators;
- redirects observed safely through an isolated analysis worker.

Do not run intrusive vulnerability scans against the suspected scammer's systems unless you own those systems or have explicit authorization from the owner.

## 6. Fake Account / Impersonation Checks

Compare public information such as:

- spelling differences in usernames;
- account creation history where publicly visible;
- mismatched contact information;
- copied public profile pictures;
- conflicting biographies or business information;
- links to unrelated domains;
- requests to move communication off-platform;
- unusual payment requests;
- differences from the legitimate account's verified links.

A mismatch is evidence to investigate, not proof of who operates the account.

## 7. If Credentials or Money Were Sent

Prioritize containment over further investigation:

- change affected passwords from a trusted device;
- enable MFA where available;
- revoke active sessions;
- contact the bank, card issuer, exchange, payment provider, or marketplace quickly;
- preserve transaction records;
- report the account to the platform;
- use the appropriate fraud-reporting or police channel when warranted.

Do not attempt to recover money by hacking, threatening, or accessing the suspected scammer's accounts.

## 8. Build the Reporting Packet

A useful packet contains:

1. case summary;
2. exact public account / URL identifiers;
3. timeline;
4. screenshots and message exports;
5. file hashes;
6. payment / transaction references if relevant;
7. public OSINT findings with source URLs;
8. observations separated from assessments;
9. unresolved questions;
10. requested action (remove impersonating account, investigate payment, preserve account records, etc.).

Avoid publishing home addresses, family details, private phone numbers, or unsupported accusations.

## 9. Reporting Destinations

Depending on the case:

- platform Trust & Safety / impersonation report;
- marketplace fraud team;
- payment provider fraud team;
- registrar / hosting abuse contact for malicious domains;
- email provider abuse desk;
- local police or national fraud-reporting service;
- internal evidence archive.

## 10. WatchDog Safety Boundary

The following belong in the public / defensive investigation path:

- OSINT;
- public username correlation;
- passive infrastructure intelligence;
- evidence hashing and preservation;
- reputation checks;
- impersonation analysis;
- reporting and takedown preparation.

The following require explicit authorization from the system owner and do not become acceptable merely because the target is suspected of scamming:

- port scanning;
- vulnerability scanning;
- login testing;
- credential attacks;
- exploit attempts;
- wireless attacks;
- access-card attacks;
- malware;
- denial of service;
- hack-back.

The goal is to expose fraudulent patterns with defensible evidence, protect the victim, and make the report easy for the appropriate platform or authority to act on.
