# Onion address discovery

WatchDog can discover publicly mentioned v3 `.onion` addresses without visiting the onion service itself.

The discovery endpoint is `POST /v1/research/onion/discover` and requires an authenticated WatchDog session. It accepts an optional topic query, a category (`all`, `news`, `government`, `media`, `privacy`, or `research`), and up to 100 deduplicated results.

Current public-source inputs include the Ahmia public Tor index, Reddit search when available, Reddit pages found through a normal web index, general web-index results, and GitHub pages found through a normal web index. Each result keeps source provenance and public mention links where available.

Discovery is intentionally separate from direct Tor retrieval. Merely finding an address does not contact the onion service. The existing onion crawler only connects when the user explicitly supplies or selects an onion address and the backend has `TOR_SOCKS_PROXY` configured.

A public mention does not establish that an onion service is authentic, online, safe, legal, or accurate. The research view excludes obvious criminal-market, credential-theft, malware-service, and abuse-material contexts rather than intentionally cataloguing them.
