"use client";

import { ChangeEvent, useMemo, useState } from "react";

export type LauncherTask = {
  id: string;
  label: string;
  description: string;
  target: string;
  accepts: "text" | "url" | "file" | "none";
};

const CATEGORIES: { id: string; label: string; description: string; tasks: LauncherTask[] }[] = [
  {
    id: "research",
    label: "Research & identity",
    description: "Work with public identifiers and network information.",
    tasks: [
      { id: "osint", label: "Search a public identifier", description: "Name, username, alias, email, phone, or domain.", target: "tool-osint", accepts: "text" },
      { id: "ip", label: "Look up a known public IP", description: "Approximate network and ASN context; never an exact home address.", target: "tool-ip", accepts: "text" },
      { id: "assistant", label: "Ask WatchDog", description: "Turn a question into a guided research starting point.", target: "tool-assistant", accepts: "text" }
    ]
  },
  {
    id: "evidence",
    label: "Evidence & files",
    description: "Bring in material from your phone without retyping it.",
    tasks: [
      { id: "triage", label: "Analyze pasted text", description: "Extract URLs, emails, IPv4 indicators, and a hash.", target: "tool-triage", accepts: "text" },
      { id: "scam", label: "Check a suspicious message", description: "Open the scam triage workflow.", target: "tool-scam", accepts: "text" },
      { id: "media", label: "Inspect a photo or file", description: "Open metadata and media inspection tools.", target: "tool-media", accepts: "file" }
    ]
  },
  {
    id: "places",
    label: "Places & vehicles",
    description: "Decode vehicles or hand an address to mapping tools.",
    tasks: [
      { id: "vin", label: "Decode a VIN", description: "Use the public NHTSA vehicle database.", target: "tool-vin", accepts: "text" },
      { id: "place", label: "Search an address or place", description: "Get map and Street View handoff links.", target: "tool-place", accepts: "text" }
    ]
  },
  {
    id: "device",
    label: "My device & privacy",
    description: "Use browser-only tools for your own device and records.",
    tasks: [
      { id: "device-lab", label: "Inspect this device", description: "Open the local device lab.", target: "tool-device", accepts: "none" },
      { id: "identity-vault", label: "Organize my research", description: "Open the private on-device identity vault.", target: "tool-vault", accepts: "none" }
    ]
  },
  {
    id: "security",
    label: "Authorized security checks",
    description: "Only for systems you own or have explicit permission to assess.",
    tasks: [
      { id: "crawl", label: "Crawl my public website", description: "Review a small number of public pages.", target: "tool-crawl", accepts: "url" },
      { id: "headers", label: "Check my site security headers", description: "Review common defensive HTTP headers.", target: "tool-webprobe", accepts: "url" },
      { id: "network", label: "Check my public host ports", description: "Run a bounded connection check with authorization confirmation.", target: "tool-netprobe", accepts: "text" }
    ]
  }
];

export default function CommandCenter({ onLaunch }: { onLaunch: (task: LauncherTask, input: string) => void }) {
  const [categoryId, setCategoryId] = useState(CATEGORIES[0].id);
  const category = CATEGORIES.find(item => item.id === categoryId) || CATEGORIES[0];
  const [taskId, setTaskId] = useState(category.tasks[0].id);
  const task = useMemo(
    () => category.tasks.find(item => item.id === taskId) || category.tasks[0],
    [category, taskId]
  );
  const [input, setInput] = useState("");
  const [fileName, setFileName] = useState("");
  const [notice, setNotice] = useState("");

  function changeCategory(event: ChangeEvent<HTMLSelectElement>) {
    const next = CATEGORIES.find(item => item.id === event.target.value) || CATEGORIES[0];
    setCategoryId(next.id);
    setTaskId(next.tasks[0].id);
    setInput("");
    setFileName("");
    setNotice("");
  }

  async function paste() {
    try {
      setInput(await navigator.clipboard.readText());
      setNotice("Pasted from your clipboard.");
    } catch {
      setNotice("Your browser blocked clipboard access. Press and hold the box to paste.");
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(input);
      setNotice("Copied.");
    } catch {
      setNotice("Select the text and use your phone's Copy command.");
    }
  }

  async function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    if (file.type.startsWith("text/") || /\.(txt|csv|json|log|md)$/i.test(file.name)) {
      setInput((await file.text()).slice(0, 250_000));
      setNotice("Text loaded from the selected file.");
    } else {
      setInput(file.name);
      setNotice("File selected. The matching tool will handle the upload.");
    }
  }

  const needsInput = task.accepts !== "none";

  return <section className="command-center" aria-labelledby="command-center-title">
    <div className="command-heading">
      <div>
        <span className="eyebrow">TASK ROUTER</span>
        <h2 id="command-center-title">What do you want WatchDog to do?</h2>
        <p>Choose a category, then a task. WatchDog opens the correct working tool and carries compatible text or links with you.</p>
      </div>
      <span className="command-mark" aria-hidden="true">WD</span>
    </div>

    <div className="command-grid">
      <label>Category
        <select value={category.id} onChange={changeCategory}>
          {CATEGORIES.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
        <small>{category.description}</small>
      </label>
      <label>Action
        <select value={task.id} onChange={event => { setTaskId(event.target.value); setInput(""); setFileName(""); setNotice(""); }}>
          {category.tasks.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
        <small>{task.description}</small>
      </label>
    </div>

    {needsInput ? <div className="command-input">
      <label htmlFor="command-value">{task.accepts === "url" ? "Paste a link" : task.accepts === "file" ? "Paste text or choose a file" : "Paste or type what you have"}</label>
      <textarea id="command-value" value={input} onChange={event => setInput(event.target.value)} placeholder={task.accepts === "url" ? "https://…" : "Paste from your phone here…"} />
      <div className="input-actions">
        <button type="button" className="secondary" onClick={paste}>Paste</button>
        <button type="button" className="secondary" onClick={copy} disabled={!input}>Copy</button>
        {(task.accepts === "file" || task.id === "triage" || task.id === "scam") ? <label className="file-button">Upload file
          <input type="file" onChange={chooseFile} accept={task.accepts === "file" ? "image/*,video/*,audio/*,.pdf,.txt,.log,.json,.csv" : ".txt,.log,.json,.csv,.eml"} />
        </label> : null}
        {fileName ? <span className="file-name">{fileName}</span> : null}
      </div>
    </div> : null}

    <div className="command-footer">
      <button type="button" onClick={() => onLaunch(task, input)} disabled={needsInput && !input.trim()}>Open {task.label}</button>
      <span role="status" aria-live="polite">{notice || "Nothing runs until you choose Open."}</span>
    </div>
  </section>;
}
