"use client";

import { useState } from "react";

const API_URL = (process.env.NEXT_PUBLIC_WATCHDOG_API_URL || "http://localhost:8000").replace(/\/$/, "");

export default function MediaInspector({ token }: { token: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function inspect() {
    if (!file || busy) return;
    setBusy(true);
    setResult("Working…");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${API_URL}/v1/media/inspect`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
        cache: "no-store",
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || body.error || `HTTP ${response.status}`);
      setResult(body);
    } catch (error: any) {
      setResult(`Error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Media Forensics</h2>
      <p>Uploads a file to the authenticated Python backend for SHA-256 hashing and image metadata inspection. Files are limited to 25 MB.</p>
      <input type="file" onChange={event => setFile(event.target.files?.[0] || null)} />
      <button onClick={inspect} disabled={!file || busy}>{busy ? "Inspecting…" : "Inspect file"}</button>
      {result !== null && <pre className="output">{typeof result === "string" ? result : JSON.stringify(result, null, 2)}</pre>}
    </section>
  );
}
