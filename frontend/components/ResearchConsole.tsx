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
    <p>Run one query across the normal web, Internet Archive, the Ahmia Tor index, or all of them together. Results are source leads, not automatic proof of a claim.</p>
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

    <label>Known .onion URL</label>
    <input value={onionUrl} onChange={event => setOnionUrl(event.target.value)} placeholder="http://56-character-v3-address.onion/" />
    <button className="secondary" disabled={!onionUrl.trim() || onionBusy} onClick={crawlOnion}>{onionBusy ? "Crawling through Tor…" : "Crawl onion site"}</button>
    {onionResult !== null && <pre className="output">{JSON.stringify(onionResult, null, 2)}</pre>}
  </section>;
}
