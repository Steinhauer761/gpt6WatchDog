"use client";

import { FormEvent, useEffect, useState } from "react";
import MediaInspector from "../components/MediaInspector";

const API_URL = (process.env.NEXT_PUBLIC_WATCHDOG_API_URL || "http://localhost:8000").replace(/\/$/, "");

type JsonValue = unknown;

function pretty(value: JsonValue) {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function request(path: string, options: RequestInit = {}, token?: string) {
  const headers = new Headers(options.headers || {});
  if (options.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers, cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || body.error || `HTTP ${response.status}`);
  return body;
}

function ToolCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <section className="card"><h2>{title}</h2><p>{description}</p>{children}</section>;
}

export default function Home() {
  const [health, setHealth] = useState<any>(null);
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [assistantText, setAssistantText] = useState("");
  const [triageText, setTriageText] = useState("");
  const [ip, setIp] = useState("");
  const [vin, setVin] = useState("");
  const [place, setPlace] = useState("");
  const [osintKind, setOsintKind] = useState("username");
  const [osintValue, setOsintValue] = useState("");
  const [probeTarget, setProbeTarget] = useState("");
  const [ports, setPorts] = useState("22,53,80,443,8080");
  const [probeUrl, setProbeUrl] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [results, setResults] = useState<Record<string, JsonValue>>({});
  const [deviceResult, setDeviceResult] = useState("");

  useEffect(() => {
    const saved = sessionStorage.getItem("watchdogSession") || "";
    if (saved) setToken(saved);
    request("/health").then(setHealth).catch(error => setHealth({ status: "error", detail: error.message }));
  }, []);

  async function login(event: FormEvent) {
    event.preventDefault();
    setLoginError("");
    try {
      const data = await request("/v1/auth/login", { method: "POST", body: JSON.stringify({ password }) });
      sessionStorage.setItem("watchdogSession", data.token);
      setToken(data.token);
      setPassword("");
    } catch (error: any) {
      setLoginError(error.message);
    }
  }

  async function run(key: string, path: string, options: RequestInit = {}) {
    setResults(current => ({ ...current, [key]: "Working…" }));
    try {
      const data = await request(path, options, token);
      setResults(current => ({ ...current, [key]: data }));
    } catch (error: any) {
      setResults(current => ({ ...current, [key]: `Error: ${error.message}` }));
    }
  }

  async function chooseBluetooth() {
    try {
      const bluetooth = (navigator as any).bluetooth;
      if (!bluetooth) throw new Error("Web Bluetooth is not available in this browser.");
      const device = await bluetooth.requestDevice({ acceptAllDevices: true, optionalServices: [] });
      setDeviceResult(pretty({ name: device.name || null, id: device.id, connected: Boolean(device.gatt?.connected) }));
    } catch (error: any) {
      setDeviceResult(`Bluetooth: ${error.message}`);
    }
  }

  async function readNfc() {
    try {
      const Reader = (window as any).NDEFReader;
      if (!Reader) throw new Error("Web NFC is not available in this browser.");
      const reader = new Reader();
      await reader.scan();
      setDeviceResult("NFC scanner armed. Hold an NDEF-compatible tag near the phone.");
      reader.onreading = (event: any) => {
        setDeviceResult(pretty({ serialNumber: event.serialNumber || null, records: event.message?.records?.map((record: any) => ({ recordType: record.recordType, mediaType: record.mediaType || null })) || [] }));
      };
    } catch (error: any) {
      setDeviceResult(`NFC: ${error.message}`);
    }
  }

  if (!token) {
    return <main className="shell"><div className="login"><h1>WatchDog</h1><p className="subtitle">Next.js frontend connected to the Python FastAPI backend.</p><form onSubmit={login}><label>Console password</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" /><button type="submit" style={{ marginTop: 12 }}>Sign in</button>{loginError && <p className="error">{loginError}</p>}</form><div className="banner">This is a real backend login. Configure WATCHDOG_ADMIN_PASSWORD and WATCHDOG_SESSION_SECRET on the Python service before use.</div></div></main>;
  }

  return <main className="shell">
    <header className="header"><div><h1>WatchDog Security Console</h1><p className="subtitle">Next.js / React interface. Application logic and secrets stay in Python FastAPI.</p></div><span className={`status ${health?.status === "ok" ? "ok" : ""}`}>{health?.status === "ok" ? `PYTHON API ${health.version} ONLINE` : "API CHECKING"}</span></header>
    <div className="banner">Every control below executes a real endpoint or a real browser capability. Active probes are limited to public systems you own or are explicitly authorized to test.</div>
    <div className="grid">
      <ToolCard title="WatchDog Assistant" description="Sends your question to OpenAI from the Python backend; the API key never enters the browser."><textarea value={assistantText} onChange={e => setAssistantText(e.target.value)} placeholder="Ask WatchDog…" /><button onClick={() => run("assistant", "/v1/assistant", { method: "POST", body: JSON.stringify({ message: assistantText, history: [] }) })}>Send</button>{results.assistant !== undefined && <pre className="output">{pretty(results.assistant)}</pre>}</ToolCard>
      <ToolCard title="Evidence Triage" description="Hashes text and extracts URLs, emails and IPv4 indicators in Python."><textarea value={triageText} onChange={e => setTriageText(e.target.value)} placeholder="Paste message, header or log text…" /><button onClick={() => run("triage", "/v1/triage/text", { method: "POST", body: JSON.stringify({ text: triageText }) })}>Analyze</button>{results.triage !== undefined && <pre className="output">{pretty(results.triage)}</pre>}</ToolCard>
      <MediaInspector token={token} />
      <ToolCard title="Public IP Intelligence" description="Looks up approximate public network location and ASN context. It does not identify a person's exact location."><input value={ip} onChange={e => setIp(e.target.value)} placeholder="8.8.8.8" /><button onClick={() => run("ip", "/v1/intel/ip", { method: "POST", body: JSON.stringify({ ip }) })}>Look up IP</button>{results.ip !== undefined && <pre className="output">{pretty(results.ip)}</pre>}</ToolCard>
      <ToolCard title="Vehicle VIN Decode" description="Queries the public NHTSA vPIC service through Python."><input value={vin} onChange={e => setVin(e.target.value.toUpperCase())} placeholder="17-character VIN" maxLength={17} /><button onClick={() => run("vin", `/v1/vehicle/vin/${encodeURIComponent(vin)}`)}>Decode VIN</button>{results.vin !== undefined && <pre className="output">{pretty(results.vin)}</pre>}</ToolCard>
      <ToolCard title="Map + Place Search" description="Queries OpenStreetMap Nominatim and returns map and Street View handoff links."><input value={place} onChange={e => setPlace(e.target.value)} placeholder="Address, landmark, city…" /><button onClick={() => run("place", `/v1/maps/geocode?q=${encodeURIComponent(place)}`)}>Search</button>{results.place !== undefined && <pre className="output">{pretty(results.place)}</pre>}</ToolCard>
      <ToolCard title="Public OSINT" description="Uses the existing Python multi-source research engine. Results are leads to verify, not identity proof."><div className="row"><select value={osintKind} onChange={e => setOsintKind(e.target.value)}><option value="name">Name</option><option value="username">Username</option><option value="alias">Alias</option><option value="email">Email</option><option value="phone">Phone</option><option value="domain">Domain</option></select><input value={osintValue} onChange={e => setOsintValue(e.target.value)} placeholder="Public identifier" /></div><button onClick={() => run("osint", "/v1/osint/search", { method: "POST", body: JSON.stringify({ identifier: osintValue, kind: osintKind, max_per_source: 6 }) })}>Search public sources</button>{results.osint !== undefined && <pre className="output">{pretty(results.osint)}</pre>}</ToolCard>
      <ToolCard title="Authorized Network Probe" description="Bounded TCP connect check against one public host. No stealth, exploitation, credentials or evasion."><input value={probeTarget} onChange={e => setProbeTarget(e.target.value)} placeholder="example.com" /><label>Ports</label><input value={ports} onChange={e => setPorts(e.target.value)} /><div className="check"><input type="checkbox" checked={authorized} onChange={e => setAuthorized(e.target.checked)} /><span>I own this target or have explicit permission to assess it.</span></div><button className="gold" disabled={!authorized} onClick={() => run("netprobe", "/v1/probe/network", { method: "POST", body: JSON.stringify({ target: probeTarget, ports: ports.split(",").map(v => Number(v.trim())).filter(Number.isInteger), authorization_confirmed: authorized }) })}>Run bounded probe</button>{results.netprobe !== undefined && <pre className="output">{pretty(results.netprobe)}</pre>}</ToolCard>
      <ToolCard title="Authorized Web Security Check" description="Checks common HTTP response security headers on a public site you are authorized to assess."><input value={probeUrl} onChange={e => setProbeUrl(e.target.value)} placeholder="https://example.com" /><button className="gold" disabled={!authorized} onClick={() => run("webprobe", "/v1/probe/web-security", { method: "POST", body: JSON.stringify({ url: probeUrl, authorization_confirmed: authorized }) })}>Check headers</button>{results.webprobe !== undefined && <pre className="output">{pretty(results.webprobe)}</pre>}</ToolCard>
      <ToolCard title="Phone Hardware" description="Direct browser-controlled hardware access. The browser always shows the device permission chooser; no pairing or network protections are bypassed."><div className="actions"><button onClick={chooseBluetooth}>Choose Bluetooth device</button><button className="secondary" onClick={readNfc}>Read NFC tag</button></div>{deviceResult && <pre className="output">{deviceResult}</pre>}</ToolCard>
    </div>
    <div className="actions"><button className="secondary" onClick={() => { sessionStorage.removeItem("watchdogSession"); setToken(""); }}>Sign out</button></div>
  </main>;
}
