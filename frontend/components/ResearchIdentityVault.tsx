"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "watchdogResearchIdentityVault";
const encoder = new TextEncoder();
const decoder = new TextDecoder();

type IdentityRecord = {
  username: string;
  email: string;
  password: string;
  notes: string;
};

type EncryptedVault = {
  version: 1;
  salt: string;
  iv: string;
  ciphertext: string;
};

function bytesToBase64(bytes: Uint8Array) {
  let binary = "";
  bytes.forEach(byte => { binary += String.fromCharCode(byte); });
  return btoa(binary);
}

function base64ToBytes(value: string) {
  const binary = atob(value);
  return Uint8Array.from(binary, char => char.charCodeAt(0));
}

function randomInt(max: number) {
  const values = new Uint32Array(1);
  crypto.getRandomValues(values);
  return values[0] % max;
}

function generateUsername() {
  const first = ["quiet", "iron", "north", "ember", "silver", "hidden", "static", "night", "cold", "plain"];
  const second = ["signal", "atlas", "ledger", "harbor", "raven", "archive", "vector", "field", "mirror", "source"];
  const suffix = String(randomInt(10000)).padStart(4, "0");
  return `${first[randomInt(first.length)]}_${second[randomInt(second.length)]}${suffix}`;
}

function generatePassword(length = 24) {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*_-+=?";
  const bytes = new Uint32Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, value => alphabet[value % alphabet.length]).join("");
}

async function deriveKey(passphrase: string, salt: Uint8Array) {
  const baseKey = await crypto.subtle.importKey("raw", encoder.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations: 250_000 },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

async function encryptRecord(record: IdentityRecord, passphrase: string): Promise<EncryptedVault> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(passphrase, salt);
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, encoder.encode(JSON.stringify(record)));
  return {
    version: 1,
    salt: bytesToBase64(salt),
    iv: bytesToBase64(iv),
    ciphertext: bytesToBase64(new Uint8Array(ciphertext)),
  };
}

async function decryptRecord(vault: EncryptedVault, passphrase: string): Promise<IdentityRecord> {
  const salt = base64ToBytes(vault.salt);
  const iv = base64ToBytes(vault.iv);
  const key = await deriveKey(passphrase, salt);
  const plaintext = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, base64ToBytes(vault.ciphertext));
  return JSON.parse(decoder.decode(plaintext));
}

export default function ResearchIdentityVault() {
  const [record, setRecord] = useState<IdentityRecord>({ username: "", email: "", password: "", notes: "" });
  const [masterPassphrase, setMasterPassphrase] = useState("");
  const [hasVault, setHasVault] = useState(false);
  const [unlocked, setUnlocked] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    setHasVault(Boolean(localStorage.getItem(STORAGE_KEY)));
  }, []);

  async function saveVault() {
    try {
      if (masterPassphrase.length < 10) throw new Error("Use a master passphrase of at least 10 characters.");
      const encrypted = await encryptRecord(record, masterPassphrase);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(encrypted));
      setHasVault(true);
      setUnlocked(true);
      setStatus("Encrypted research identity saved locally on this browser.");
    } catch (error: any) {
      setStatus(error.message || "Could not save vault.");
    }
  }

  async function unlockVault() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) throw new Error("No saved research identity exists on this browser.");
      const decrypted = await decryptRecord(JSON.parse(raw), masterPassphrase);
      setRecord(decrypted);
      setUnlocked(true);
      setStatus("Vault unlocked locally.");
    } catch {
      setUnlocked(false);
      setStatus("Could not unlock the vault. Check the master passphrase.");
    }
  }

  function lockVault() {
    setRecord({ username: "", email: "", password: "", notes: "" });
    setMasterPassphrase("");
    setUnlocked(false);
    setStatus("Vault locked.");
  }

  function deleteVault() {
    localStorage.removeItem(STORAGE_KEY);
    setRecord({ username: "", email: "", password: "", notes: "" });
    setMasterPassphrase("");
    setUnlocked(false);
    setHasVault(false);
    setStatus("Saved research identity deleted from this browser.");
  }

  async function copy(value: string, label: string) {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setStatus(`${label} copied.`);
  }

  return <section className="card">
    <h2>Research Identity Vault</h2>
    <p>Create a separate research username, password and dedicated email identity. The profile is encrypted in this browser with your master passphrase and is never sent to the WatchDog backend.</p>

    <label>Master passphrase</label>
    <input type="password" value={masterPassphrase} onChange={event => setMasterPassphrase(event.target.value)} autoComplete="new-password" placeholder="Used only to encrypt/decrypt this local vault" />

    {hasVault && !unlocked && <div className="actions"><button onClick={unlockVault} disabled={!masterPassphrase}>Unlock vault</button></div>}

    {(!hasVault || unlocked) && <>
      <label>Research username</label>
      <div className="row">
        <input value={record.username} onChange={event => setRecord(current => ({ ...current, username: event.target.value }))} placeholder="Dedicated research alias" />
        <button className="secondary" onClick={() => setRecord(current => ({ ...current, username: generateUsername() }))}>Generate</button>
      </div>

      <label>Dedicated email</label>
      <input type="email" value={record.email} onChange={event => setRecord(current => ({ ...current, email: event.target.value }))} placeholder="Create a separate mailbox elsewhere, then enter it here" />

      <label>Research password</label>
      <div className="row">
        <input type="text" value={record.password} onChange={event => setRecord(current => ({ ...current, password: event.target.value }))} autoComplete="off" placeholder="Use only for this research identity" />
        <button className="secondary" onClick={() => setRecord(current => ({ ...current, password: generatePassword() }))}>Generate strong password</button>
      </div>

      <label>Notes</label>
      <textarea value={record.notes} onChange={event => setRecord(current => ({ ...current, notes: event.target.value }))} placeholder="Recovery notes that do not identify your normal accounts" />

      <div className="actions">
        <button onClick={saveVault} disabled={!masterPassphrase}>Encrypt + save locally</button>
        <button className="secondary" onClick={() => copy(record.username, "Username")}>Copy username</button>
        <button className="secondary" onClick={() => copy(record.password, "Password")}>Copy password</button>
        {unlocked && <button className="secondary" onClick={lockVault}>Lock</button>}
        {hasVault && <button className="secondary" onClick={deleteVault}>Delete local vault</button>}
      </div>
    </>}

    <div className="banner" style={{ marginTop: 12 }}>This tool does not create an email account for you. Use a dedicated mailbox you control, do not reuse your normal passwords, and do not put identifying recovery information into the research profile.</div>
    {status && <div className="output">{status}</div>}
  </section>;
}
