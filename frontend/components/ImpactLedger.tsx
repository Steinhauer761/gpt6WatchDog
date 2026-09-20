"use client";

import { useEffect, useMemo, useState } from "react";

type Metrics = {
  scamPostsReviewed: number;
  peopleWarned: number;
  accountsReported: number;
  peopleDisengaged: number;
  evidencePackages: number;
  confirmedIndicators: number;
  disprovedIndicators: number;
};

const EMPTY_METRICS: Metrics = { scamPostsReviewed: 0, peopleWarned: 0, accountsReported: 0, peopleDisengaged: 0, evidencePackages: 0, confirmedIndicators: 0, disprovedIndicators: 0 };
const METRIC_LABELS: Array<[keyof Metrics, string]> = [
  ["scamPostsReviewed", "Scam posts reviewed"],
  ["peopleWarned", "People warned"],
  ["accountsReported", "Accounts reported or removed"],
  ["peopleDisengaged", "People who stopped contact"],
  ["evidencePackages", "Evidence packages submitted"],
  ["confirmedIndicators", "Indicators confirmed"],
  ["disprovedIndicators", "Indicators disproved"],
];
const STORAGE_KEY = "watchdogImpactLedgerV1";

function safeCount(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? Math.floor(parsed) : 0;
}

export default function ImpactLedger() {
  const [metrics, setMetrics] = useState<Metrics>(EMPTY_METRICS);
  const [caseId, setCaseId] = useState("");
  const [incidentTime, setIncidentTime] = useState("");
  const [copied, setCopied] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved && typeof saved === "object") setMetrics(Object.fromEntries(METRIC_LABELS.map(([key]) => [key, safeCount(saved[key])])) as Metrics);
    } catch { /* Ignore a corrupt local value and start with a clean ledger. */ }
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (loaded) localStorage.setItem(STORAGE_KEY, JSON.stringify(metrics));
  }, [loaded, metrics]);

  const notice = useMemo(() => {
    const reference = caseId.trim() || "[case reference]";
    const timestamp = incidentTime ? new Date(incidentTime).toISOString() : "[UTC timestamp]";
    return `WatchDog incident ${reference} was recorded at ${timestamp}. Relevant content, account identifiers, and timestamps supplied with the report have been preserved. Further contact or activity may be added to the record and reported to the appropriate platform or service provider.`;
  }, [caseId, incidentTime]);

  function updateMetric(key: keyof Metrics, value: string) {
    setMetrics(current => ({ ...current, [key]: safeCount(value) }));
  }

  async function copyNotice() {
    await navigator.clipboard.writeText(notice);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function exportLedger() {
    const payload = { schema: "watchdog-impact-ledger/v1", exportedAt: new Date().toISOString(), metrics };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `watchdog-impact-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return <>
    <section className="card impact-card">
      <h2>Impact Ledger</h2>
      <p>Record anonymized outcomes on this device. Counts persist in this browser and can be exported as a dated JSON record.</p>
      <div className="impact-metrics">
        {METRIC_LABELS.map(([key, label]) => <label key={key}><span>{label}</span><input type="number" min="0" step="1" inputMode="numeric" value={metrics[key]} onChange={event => updateMetric(key, event.target.value)} /></label>)}
      </div>
      <div className="actions"><button onClick={exportLedger}>Export ledger</button></div>
      <p className="privacy-note">Use totals only. Do not enter victim names or private identifiers here.</p>
    </section>
    <section className="card">
      <h2>Factual Case Notice</h2>
      <p>Create a truthful preservation notice. It does not claim location tracking, device access, police involvement, or identity verification.</p>
      <div className="row">
        <div><label htmlFor="case-id">Case reference</label><input id="case-id" value={caseId} onChange={event => setCaseId(event.target.value)} placeholder="WD-1042" /></div>
        <div><label htmlFor="incident-time">Incident time</label><input id="incident-time" type="datetime-local" value={incidentTime} onChange={event => setIncidentTime(event.target.value)} /></div>
      </div>
      <div className="output notice-output">{notice}</div>
      <div className="actions"><button onClick={copyNotice}>{copied ? "Copied" : "Copy notice"}</button></div>
    </section>
  </>;
}
