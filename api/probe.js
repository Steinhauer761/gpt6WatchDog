import dns from 'node:dns/promises';
import net from 'node:net';
import tls from 'node:tls';

export const config = { maxDuration: 20 };

function json(res, status, body) {
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, private');
  return res.status(status).json(body);
}

function normalizeTarget(raw) {
  let value = String(raw || '').trim();
  if (!value) throw new Error('Target is required');
  if (!/^https?:\/\//i.test(value)) value = `https://${value}`;
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Use an http(s) target');
  if (!url.hostname || url.username || url.password) throw new Error('Invalid target');
  return { hostname: url.hostname.toLowerCase(), requestedUrl: url };
}

function isPrivateIPv4(ip) {
  const p = ip.split('.').map(Number);
  if (p.length !== 4 || p.some(n => !Number.isInteger(n) || n < 0 || n > 255)) return true;
  const [a,b] = p;
  return a === 10 || a === 127 || a === 0 ||
    (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168) ||
    (a === 100 && b >= 64 && b <= 127) ||
    (a >= 224);
}

function isPrivateIp(ip) {
  const family = net.isIP(ip);
  if (family === 4) return isPrivateIPv4(ip);
  if (family === 6) {
    const s = ip.toLowerCase();
    return s === '::1' || s === '::' || s.startsWith('fc') || s.startsWith('fd') || s.startsWith('fe80:');
  }
  return true;
}

async function safeFetch(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const r = await fetch(url, {
      method: 'HEAD',
      redirect: 'manual',
      signal: controller.signal,
      headers: { 'User-Agent': 'WatchDog-Authorized-Probe/0.4' },
    });
    return {
      url,
      status: r.status,
      status_text: r.statusText,
      server: r.headers.get('server'),
      content_type: r.headers.get('content-type'),
      location: r.headers.get('location'),
      hsts: r.headers.get('strict-transport-security'),
    };
  } catch (e) {
    return { url, error: e?.name === 'AbortError' ? 'timeout' : String(e?.message || 'request failed') };
  } finally {
    clearTimeout(timer);
  }
}

function tlsSummary(hostname) {
  return new Promise(resolve => {
    const socket = tls.connect({ host: hostname, port: 443, servername: hostname, rejectUnauthorized: false, timeout: 7000 }, () => {
      const cert = socket.getPeerCertificate(true) || {};
      resolve({
        protocol: socket.getProtocol() || null,
        authorized: socket.authorized,
        authorization_error: socket.authorizationError || null,
        subject: cert.subject || null,
        issuer: cert.issuer || null,
        valid_from: cert.valid_from || null,
        valid_to: cert.valid_to || null,
        fingerprint256: cert.fingerprint256 || null,
      });
      socket.end();
    });
    socket.on('timeout', () => { socket.destroy(); resolve({ error: 'timeout' }); });
    socket.on('error', e => resolve({ error: String(e.message || 'TLS connection failed') }));
  });
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return json(res, 405, { error: 'Use POST' });
  }

  if (req.body?.authorization_confirmed !== true) {
    return json(res, 400, { error: 'Confirm that you own this target or have explicit authorization to test it.' });
  }

  let target;
  try { target = normalizeTarget(req.body?.target); }
  catch (e) { return json(res, 400, { error: e.message }); }

  let addresses;
  try {
    addresses = await dns.lookup(target.hostname, { all: true, verbatim: true });
  } catch {
    return json(res, 400, { error: 'DNS lookup failed for this target.' });
  }

  if (!addresses.length || addresses.some(x => isPrivateIp(x.address))) {
    return json(res, 400, { error: 'Targets resolving to private, loopback, link-local or reserved addresses are blocked.' });
  }

  const httpsUrl = `https://${target.hostname}/`;
  const httpUrl = `http://${target.hostname}/`;
  const [https, http, tlsInfo] = await Promise.all([
    safeFetch(httpsUrl),
    safeFetch(httpUrl),
    tlsSummary(target.hostname),
  ]);

  return json(res, 200, {
    target: target.hostname,
    scope: 'basic authorized web probe',
    resolved_addresses: addresses.map(x => ({ address: x.address, family: x.family })),
    https,
    http,
    tls: tlsInfo,
    note: 'This probe is intentionally limited to DNS resolution, HTTP(S) response metadata and TLS certificate inspection. It does not perform exploitation, credential testing or broad port scanning.',
  });
}
