"use client";

import { useEffect, useMemo, useState } from "react";

const API_URL = (process.env.NEXT_PUBLIC_WATCHDOG_API_URL || "http://localhost:8000").replace(/\/$/, "");
const LIBRARY_KEY = "watchdogMediaReferenceLibrary";

type MediaKind = "video" | "audio" | "image";

type SearchResult = {
  id: string;
  source: string;
  title: string;
  kind: MediaKind;
  mime?: string;
  direct_url?: string;
  thumbnail_url?: string;
  source_url: string;
  creator?: string;
  license?: string;
  license_url?: string;
  credit?: string;
};

type SavedReference = SearchResult & { saved_at: string };

function readLibrary(): SavedReference[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(LIBRARY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export default function MediaStudio({ token }: { token: string }) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<MediaKind>("video");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [rightsNote, setRightsNote] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [library, setLibrary] = useState<SavedReference[]>([]);

  const [video, setVideo] = useState<File | null>(null);
  const [music, setMusic] = useState<File | null>(null);
  const [startSeconds, setStartSeconds] = useState("0");
  const [endSeconds, setEndSeconds] = useState("0");
  const [aspect, setAspect] = useState("9:16");
  const [speed, setSpeed] = useState("1");
  const [caption, setCaption] = useState("");
  const [musicVolume, setMusicVolume] = useState("0.8");
  const [rendering, setRendering] = useState(false);
  const [renderError, setRenderError] = useState("");
  const [renderUrl, setRenderUrl] = useState("");

  useEffect(() => setLibrary(readLibrary()), []);

  useEffect(() => {
    return () => {
      if (renderUrl) URL.revokeObjectURL(renderUrl);
    };
  }, [renderUrl]);

  const videoPreviewUrl = useMemo(() => video ? URL.createObjectURL(video) : "", [video]);
  useEffect(() => {
    return () => {
      if (videoPreviewUrl) URL.revokeObjectURL(videoPreviewUrl);
    };
  }, [videoPreviewUrl]);

  async function searchMedia() {
    if (!query.trim()) return;
    setSearching(true);
    setSearchError("");
    try {
      const response = await fetch(`${API_URL}/v1/media/search?q=${encodeURIComponent(query.trim())}&kind=${kind}&limit=12`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
      setResults(body.results || []);
      setRightsNote(body.rights_note || "");
    } catch (error: any) {
      setSearchError(error.message || "Search failed");
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  function saveReference(item: SearchResult) {
    const next: SavedReference[] = [
      { ...item, saved_at: new Date().toISOString() },
      ...library.filter(existing => existing.id !== item.id),
    ].slice(0, 200);
    localStorage.setItem(LIBRARY_KEY, JSON.stringify(next));
    setLibrary(next);
  }

  function removeReference(id: string) {
    const next = library.filter(item => item.id !== id);
    localStorage.setItem(LIBRARY_KEY, JSON.stringify(next));
    setLibrary(next);
  }

  async function renderVideo() {
    if (!video) {
      setRenderError("Choose a source video first.");
      return;
    }
    setRendering(true);
    setRenderError("");
    if (renderUrl) {
      URL.revokeObjectURL(renderUrl);
      setRenderUrl("");
    }

    const form = new FormData();
    form.append("video", video);
    if (music) form.append("music", music);
    form.append("start_seconds", startSeconds || "0");
    form.append("end_seconds", endSeconds || "0");
    form.append("aspect", aspect);
    form.append("speed", speed || "1");
    form.append("caption", caption);
    form.append("music_volume", musicVolume || "0.8");

    try {
      const response = await fetch(`${API_URL}/v1/media/render`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${response.status}`);
      }
      const blob = await response.blob();
      setRenderUrl(URL.createObjectURL(blob));
    } catch (error: any) {
      setRenderError(error.message || "Render failed");
    } finally {
      setRendering(false);
    }
  }

  return <section className="card" style={{ gridColumn: "1 / -1" }}>
    <h2>WatchDog Media Creator</h2>
    <p>Search reusable media, keep a source-and-license library, edit a real video, and render an MP4 through the Python backend. The current renderer handles trim, TikTok/vertical, square or widescreen framing, speed, a burned-in caption, and an optional replacement music track.</p>

    <div className="row">
      <div>
        <label>Search open media</label>
        <input value={query} onChange={e => setQuery(e.target.value)} placeholder="city night rain, old television, dramatic piano…" onKeyDown={e => { if (e.key === "Enter") searchMedia(); }} />
      </div>
      <div>
        <label>Media type</label>
        <select value={kind} onChange={e => setKind(e.target.value as MediaKind)}>
          <option value="video">Video</option>
          <option value="audio">Audio / music</option>
          <option value="image">Image</option>
        </select>
      </div>
    </div>
    <div className="actions"><button onClick={searchMedia} disabled={searching || !query.trim()}>{searching ? "Searching…" : "Search Wikimedia + Internet Archive"}</button></div>
    {searchError && <p className="error">{searchError}</p>}
    {rightsNote && <div className="banner">{rightsNote}</div>}

    {results.length > 0 && <div className="media-results">
      {results.map(item => <article className="media-result" key={item.id}>
        {item.thumbnail_url && <img src={item.thumbnail_url} alt="" loading="lazy" />}
        <strong>{item.title}</strong>
        <span>{item.source}{item.creator ? ` · ${item.creator}` : ""}</span>
        <span>{item.license || "License not supplied by source"}</span>
        <div className="actions">
          <button className="secondary" onClick={() => saveReference(item)}>Save to library</button>
          <a className="button-link" href={item.source_url} target="_blank" rel="noreferrer">Source + rights</a>
          {item.direct_url && <a className="button-link" href={item.direct_url} target="_blank" rel="noreferrer">Open media</a>}
        </div>
      </article>)}
    </div>}

    <h3 className="section-heading">Reference library</h3>
    <p>Saved references stay on this browser with their source and license information. That keeps the research organized without copying copyrighted catalogs into WatchDog.</p>
    {library.length === 0 ? <div className="banner">Your media reference library is empty.</div> : <div className="media-library">
      {library.slice(0, 12).map(item => <div className="media-library-item" key={item.id}>
        <div><strong>{item.title}</strong><span>{item.kind} · {item.source} · {item.license || "rights unknown"}</span></div>
        <div className="actions"><a className="button-link" href={item.source_url} target="_blank" rel="noreferrer">Source</a><button className="secondary" onClick={() => removeReference(item.id)}>Remove</button></div>
      </div>)}
    </div>}

    <h3 className="section-heading">Editor + MP4 render</h3>
    <div className="row">
      <div><label>Source video</label><input type="file" accept="video/*" onChange={e => setVideo(e.target.files?.[0] || null)} /></div>
      <div><label>Optional music track (replaces source audio in v1)</label><input type="file" accept="audio/*" onChange={e => setMusic(e.target.files?.[0] || null)} /></div>
    </div>
    {videoPreviewUrl && <div className="media-preview"><video src={videoPreviewUrl} controls playsInline /></div>}
    <div className="row">
      <div><label>Trim start (seconds)</label><input type="number" min="0" step="0.1" value={startSeconds} onChange={e => setStartSeconds(e.target.value)} /></div>
      <div><label>Trim end (0 = to end)</label><input type="number" min="0" step="0.1" value={endSeconds} onChange={e => setEndSeconds(e.target.value)} /></div>
    </div>
    <div className="row">
      <div><label>Canvas</label><select value={aspect} onChange={e => setAspect(e.target.value)}><option value="9:16">9:16 TikTok / Reels / Shorts</option><option value="1:1">1:1 Square</option><option value="16:9">16:9 Widescreen</option></select></div>
      <div><label>Speed</label><select value={speed} onChange={e => setSpeed(e.target.value)}><option value="0.5">0.5×</option><option value="0.75">0.75×</option><option value="1">1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></div>
    </div>
    <label>Caption burned into video</label>
    <input value={caption} onChange={e => setCaption(e.target.value)} maxLength={500} placeholder="Optional caption or quote" />
    <label>Music volume</label>
    <input type="number" min="0" max="2" step="0.1" value={musicVolume} onChange={e => setMusicVolume(e.target.value)} />
    <div className="actions"><button className="gold" onClick={renderVideo} disabled={!video || rendering}>{rendering ? "Rendering in Python…" : "Render MP4"}</button></div>
    {renderError && <p className="error">{renderError}</p>}
    {renderUrl && <div className="media-preview"><video src={renderUrl} controls playsInline /><div className="actions"><a className="button-link" href={renderUrl} download="watchdog-media-edit.mp4">Save rendered MP4</a></div></div>}
  </section>;
}
