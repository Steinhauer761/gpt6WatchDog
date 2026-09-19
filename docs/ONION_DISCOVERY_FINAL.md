# Onion discovery feature summary

This branch adds an authenticated, non-mock onion-address discovery feature to WatchDog. It aggregates public v3 `.onion` mentions from multiple public sources, deduplicates them, preserves provenance, supports topic/category filtering, returns up to 100 addresses per run, and hands selected addresses to the existing bounded Tor crawler.
