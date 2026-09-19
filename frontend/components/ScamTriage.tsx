"use client";

import { useState } from "react";

const API_URL = (process.env.NEXT_PUBLIC_WATCHDOG_API_URL || "http://localhost:8000").replace(/\/$/, "");

type Result = {
  score?: number;
  disposition?: string;
  summary?: string;
  factors?: Array<{ points?: number; reason?: string; evidence?: string }>;
  evidence_sha256?: string;
  report_packet?: {
    automatic_submission?: { submitted?: boolean; reason?: string };
    canada_destinations?: Array<{ name?: string; url?: string }>;
  };
  deterrence?: { recommended?: string; message?: string };
};

async function post(path: string, token: string, body: unknown) {
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

export default function ScamTriage({ token }: { token: string }) {
  const [number, setNumber] = useState("");
  const [channel, setChannel] = useState("call");
  const [receivedAt, setReceivedAt] = useState("");
  const [claimedIdentity, setClaimedIdentity] = useState("");
  const [message, setMessage] = useState("");
  const [repeatCount, setRepeatCount] = useState(1);
  const [flags, setFlags] = useState({
    unsolicited: true,
    requested_money: false,
    requested_credentials: false,
    claimed_organization: false,
    threat_or_urgency: false,
    caller_id_mismatch: false,
    known_scam_pattern: false,
  });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [copyStatus, setCopyStatus] = useState("");

  function toggle(key: keyof typeof flags) {
    setFlags(current => ({ ...current, [key]: !current[key] }));
  }

  async function analyze() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const data = await post("/v1/scam/triage", token, {
        number,
        channel,
        received_at: receivedAt,
        claimed_identity: claimedIdentity,
        message,
        repeat_count: repeatCount,
        ...flags,
      });
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Triage failed");
    } finally {
      setBusy(false);
    }
  }

  async function copyDeterrence() {
    const text = result?.deterrence?.message;
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopyStatus("Screening notice copied.");
  }

  const dispositionLabel = result?.score === 5
    ? "UNCERTAIN"
    : (result?.score || 0) >= 6
      ? "REPORTABLE"
      : "NOT REPORTABLE";

  return <section className="card">
    <h2>Scam / Spoofing Reportability</h2>
    <p>Scores the incident from 1–10 based on the evidence you enter. The score measures whether the incident is worth reporting; it does not identify the subscriber behind a displayed phone number as the scammer.</p>

    <div className="row">
      <input value={number} onChange={event => setNumber(event.target.value)} placeholder="Displayed phone number" />
      <select value={channel} onChange={event => setChannel(event.target.value)}>
        <option value="call">Call</option>
        <option value="sms">Text / SMS</option>
        <option value="voicemail">Voicemail</option>
        <option value="messaging">Messaging app</option>
      </select>
    </div>

    <label>Date / time received</label>
    <input value={receivedAt} onChange={event => setReceivedAt(event.target.value)} placeholder="e.g. 2026-09-19 14:32" />

    <label>Who they claimed to be</label>
    <input value={claimedIdentity} onChange={event => setClaimedIdentity(event.target.value)} placeholder="Bank, CRA, telecom, delivery company, person, etc." />

    <label>Message / call notes</label>
    <textarea value={message} onChange={event => setMessage(event.target.value)} placeholder="Paste the text or summarize what they said and asked for." />

    <label>Repeat contacts</label>
    <input type="number" min={1} max={999} value={repeatCount} onChange={event => setRepeatCount(Math.max(1, Number(event.target.value) || 1))} />

    <div className="check"><input type="checkbox" checked={flags.unsolicited} onChange={() => toggle("unsolicited")} /><span>Unsolicited contact</span></div>
    <div className="check"><input type="checkbox" checked={flags.requested_money} onChange={() => toggle("requested_money")} /><span>Asked for money, crypto, gift cards, transfer, or payment</span></div>
    <div className="check"><input type="checkbox" checked={flags.requested_credentials} onChange={() => toggle("requested_credentials")} /><span>Asked for a password, PIN, verification code, login, or remote access</span></div>
    <div className="check"><input type="checkbox" checked={flags.claimed_organization} onChange={() => toggle("claimed_organization")} /><span>Claimed to represent a government body, bank, telecom, or major company</span></div>
    <div className="check"><input type="checkbox" checked={flags.threat_or_urgency} onChange={() => toggle("threat_or_urgency")} /><span>Used threats, urgency, suspension, arrest, shutoff, or similar pressure</span></div>
    <div className="check"><input type="checkbox" checked={flags.caller_id_mismatch} onChange={() => toggle("caller_id_mismatch")} /><span>Caller identity did not match a verified official number/contact route</span></div>
    <div className="check"><input type="checkbox" checked={flags.known_scam_pattern} onChange={() => toggle("known_scam_pattern")} /><span>Matches a scam pattern you have independently recognized</span></div>

    <button onClick={analyze} disabled={busy || (!number.trim() && !message.trim())}>{busy ? "Scoring…" : "Score incident"}</button>
    {error && <p className="error">{error}</p>}

    {result && <div className="output">
      <h3>{result.score}/10 · {dispositionLabel}</h3>
      <div>{result.summary}</div>
      {(result.factors || []).length > 0 && <div style={{ marginTop: 10 }}>
        {(result.factors || []).map((factor, index) => <div key={`${factor.reason}-${index}`} style={{ marginTop: 6 }}>
          <strong>+{factor.points}: {factor.reason}</strong>{factor.evidence ? <div>{factor.evidence}</div> : null}
        </div>)}
      </div>}
      {result.evidence_sha256 && <div style={{ marginTop: 10 }}>Evidence packet SHA-256: <code>{result.evidence_sha256}</code></div>}

      {(result.score || 0) >= 6 && <>
        <h3 style={{ marginTop: 14 }}>Report packet ready</h3>
        <div>{result.report_packet?.automatic_submission?.reason}</div>
        {(result.report_packet?.canada_destinations || []).map((destination, index) => destination.url ? <div key={`${destination.name}-${index}`} style={{ marginTop: 6 }}><a href={destination.url} target="_blank" rel="noreferrer">{destination.name}</a></div> : null)}
      </>}

      {result.deterrence?.message && <>
        <h3 style={{ marginTop: 14 }}>Safe deterrence notice</h3>
        <div>{result.deterrence.recommended}</div>
        <blockquote>{result.deterrence.message}</blockquote>
        <button className="secondary" onClick={copyDeterrence}>Copy screening notice</button>
        {copyStatus && <div>{copyStatus}</div>}
      </>}
    </div>}

    <div className="banner" style={{ marginTop: 12 }}>Scale: 1–4 = not reportable, 5 = uncertain, 6–10 = reportable. Because caller ID can be spoofed, WatchDog reports the incident and evidence rather than accusing the subscriber who owns the displayed number.</div>
  </section>;
}
