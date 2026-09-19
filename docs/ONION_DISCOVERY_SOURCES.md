# Onion discovery source behavior

WatchDog's onion-address discovery is source aggregation, not a directory of vetted services.

It queries:

- Ahmia's public Tor index for topic-related v3 onion addresses.
- Reddit's public search endpoint when it responds without blocking or throttling.
- Normal-web search results that mention Reddit posts and `.onion` addresses.
- Normal-web results that mention `.onion` addresses generally.
- GitHub pages surfaced by a normal-web index that publicly mention `.onion` addresses.

Results are deduplicated by onion host and sorted by the number of distinct source types and public mentions. Upstream sources may rate-limit, block automated requests, remove old posts, or contain stale addresses, so source errors are returned instead of being hidden.
