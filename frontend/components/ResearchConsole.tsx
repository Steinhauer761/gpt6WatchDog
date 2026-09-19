"use client";

import { useState } from "react";

const API_URL = (process.env.NEXT_PUBLIC_WATCHDOG_API_URL || "http://localhost:8000").replace(/\/$/, "");

type SearchResult = {
  surface?: string;
  source?: string;
  title?: string;
  url?: string;
  snippet?: string | null;
  media_type?: string | null;
  date?: string | null;
  creator?: string | string[] | null;
};

type SearchResponse = {
  query?: string;
  scope?: string;
  result_count?: number;
  results?: SearchResult[];
  source_errors?: unknown[];
  note?: string;
};

type OnionMention = {
  source?: string;
  source_url?: string;
  title?: string;
  snippet?: string;
  community?: string;
};

type OnionDiscoveryItem = {
  url?: string;
  host?: string;
  title?: string;
  mention_count?: number;
  source_count?: number;
  sources?: string[];
  mentions?: OnionMention[];
};

type OnionDiscoveryResponse = {
  query?: string | null;
  category?: string;
  result_count?: number;
  results?: OnionDiscoveryItem[];
  source_errors?: unknown[];
  note?: string;
};

async function api(path: string, token: string, body: unknown) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

export default function ResearchConsole({ token }: { token: string }) {
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("both");
  const [searching, setSearching] = useState(false);
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searchError, setSearchError] = useState("");

  const [discoverQuery, setDiscoverQuery] = useState("");
  const [discoverCategory, setDiscoverCategory] = useState("all");
  const [discoverBusy, setDiscoverBusy] = useState(false);
  const [discoverResult, setDiscoverResult] = useState<OnionDiscoveryResponse | null>(null);
  const [discoverError, setDiscoverError] = useState("");

  const [onionUrl, setOnionUrl] = useState("");
  const [onionResult, setOnionResult] = useState<unknown>(null);
  const [onionBusy, setOnionBusy] = useState(false);

  async function runSearch() {
    setSearching(true);
    setSearchError("");
    try {
      setSearchResult(await api("/v1/research/search", token, { query, scope, max_results: 12 }));
    } catch (error: any) {
      setSearchError(error.message);
      setSearchResult(null);
    } finally {
      setSearching(false);
    }
  }

  async function discoverOnions() {
    setDiscoverBusy(true);
    setDiscoverError("");
    try {
      setDiscoverResult(await api("/v1/research/onion/discover", token, {
        query: discoverQuery,
        category: discoverCategory,
        max_results: 100,
      }));
    } catch (error: any) {
      setDiscoverError(error.message);
      setDiscoverResult(null);
    } finally {
      setDiscoverBusy(false);
    }
  }

  async function crawlOnion() {
    setOnionBusy(true);
    setOnionResult(null);
    try {
      setOnionResult(await api("/v1/research/onion/crawl", token, { url: onionUrl, max_pages: 8, max_depth: 1 }));
    } catch (error: any) {
      setOnionResult({ error: error.message });
    } finally {
      setOnionBusy(false);
    }
  }

  return <section className="card">
    <h2>Web + Tor Research</h2>
    <p>Search the normal web, Internet Archive, the Ahmia Tor index, or all of them together. Results are source leads, not automatic proof of a claim.</p>

    <div className="row">
      <select value={scope} onChange={event => setScope(event.target.value)}>
        <option value="both">Web + Tor + Archive</option>
        <option value="web">Web + Archive</option>
        <option value="tor">Tor index only</option>
      </select>
      <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Documents, videos, event, quoted phrase…" />
    </div>
    <button disabled={!query.trim() || searching} onClick={runSearch}>{searching ? "Searching…" : "Search sources"}</button>
    {searchError && <p className="error">{searchError}</p>}
    {searchResult && <div className="output">
      <div>{searchResult.result_count || 0} results for “{searchResult.query}”</div>
      {(searchResult.results || []).map((item, index) => <div key={`${item.url || item.title}-${index}`} style={{ marginTop: 12 }}>
        <strong>{item.title || item.url || "Untitled result"}</strong>
        <div>{item.source || "Source"} · {item.surface || "web"}{item.media_type ? ` · ${item.media_type}` : ""}</div>
        {item.url?.endsWith(".onion") || item.url?.includes(".onion/") ? <code>{item.url}</code> : item.url ? <a href={item.url} target="_blank" rel="noreferrer">{item.url}</a> : null}
        {item.snippet && <div>{item.snippet}</div>}
      </div>)}
      {searchResult.note && <div style={{ marginTop: 12 }}>{searchResult.note}</div>}
    </div>}

    <hr style={{ margin: "20px 0", opacity: 0.25 }} />
    <h3>Discover Publicly Mentioned Onion Addresses</h3>
    <p>Collects public v3 .onion mentions from Reddit, web indexes, GitHub-indexed pages and Ahmia, deduplicates them, and keeps the source links so you can see where each address came from.</p>
    <div className="row">
      <select value={discoverCategory} onChange={event => setDiscoverCategory(event.target.value)}>
        <option value="all">All research sources</option>
        <option value="news">News / journalism</option>
        <option value="government">Government / public records</option>
        <option value="media">Media / archives</option>
        <option value="privacy">Privacy / whistleblowing</option>
        <option value="research">Research / documents</option>
      </select>
      <input value={discoverQuery} onChange={event => setDiscoverQuery(event.target.value)} placeholder="Optional topic, phrase, event or subject" />
    </div>
    <button onClick={discoverOnions} disabled={discoverBusy}>{discoverBusy ? "Discovering…" : "Find onion addresses"}</button>
    {discoverError && <p className="error">{discoverError}</p>}
    {discoverResult && <div className="output">
      <div>{discoverResult.result_count || 0} unique onion addresses found</div>
      {(discoverResult.results || []).map((item, index) => <div key={`${item.host || item.url}-${index}`} style={{ marginTop: 14 }}>
        <strong>{item.title || item.host || "Onion service"}</strong>
        <div>{item.source_count || 0} source types · {item.mention_count || 0} public mentions</div>
        {item.url && <code style={{ display: "block", overflowWrap: "anywhere" }}>{item.url}</code>}
        {(item.sources || []).length > 0 && <div>Sources: {(item.sources || []).join(", ")}</div>}
        {(item.mentions || []).slice(0, 3).map((mention, mentionIndex) => <div key={`${mention.source_url || mention.title}-${mentionIndex}`} style={{ marginTop: 8 }}>
          <span>{mention.community ? `${mention.community} · ` : ""}{mention.source || "Source"}</span>
          {mention.source_url && <div><a href={mention.source_url} target="_blank" rel="noreferrer">View public mention</a></div>}
          {mention.title && <div>{mention.title}</div>}
        </div>)}
        {item.url && <button className="secondary" style={{ marginTop: 8 }} onClick={() => setOnionUrl(item.url || "")}>Use in onion crawler</button>}
      </div>)}
      {discoverResult.note && <div style={{ marginTop: 12 }}>{discoverResult.note}</div>}
    </div>}

    <hr style={{ margin: "20px 0", opacity: 0.25 }} />
    <label>Known .onion URL</label>
    <input value={onionUrl} onChange={event => setOnionUrl(event.target.value)} placeholder="http://56-character-v3-address.onion/" />
    <button className="secondary" disabled={!onionUrl.trim() || onionBusy} onClick={crawlOnion}>{onionBusy ? "Crawling through Tor…" : "Crawl onion site"}</button>
    {onionResult !== null && <pre className="output">{JSON.stringify(onionResult, null, 2)}</pre>}
  </section>;
}
