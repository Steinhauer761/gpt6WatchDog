# Onion discovery request examples

Discover broadly across research-oriented public mentions:

```json
{"query":"","category":"all","max_results":100}
```

Find onion addresses publicly mentioned around journalism or current-events research:

```json
{"query":"investigative journalism","category":"news","max_results":100}
```

Find public-record and government-document research sources:

```json
{"query":"public records","category":"government","max_results":100}
```

The endpoint returns deduplicated v3 onion addresses plus the public sources that mentioned them. It does not automatically visit those onion services.
