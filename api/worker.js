const DEFAULT_WORKER_URL = 'https://gpt6watchdog-2.onrender.com';

export const config = { maxDuration: 60 };

function json(res, status, body) {
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, private');
  res.setHeader('Pragma', 'no-cache');
  return res.status(status).json(body);
}

function cleanBaseUrl(value) {
  const raw = String(value || DEFAULT_WORKER_URL).trim();
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:') return DEFAULT_WORKER_URL;
    return url.origin;
  } catch {
    return DEFAULT_WORKER_URL;
  }
}

async function readJsonResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); }
  catch { return { detail: text.slice(0, 4000) }; }
}

export default async function handler(req, res) {
  const action = String(req.query.action || '').trim().toLowerCase();
  const workerUrl = cleanBaseUrl(process.env.WATCHDOG_WORKER_URL);
  const apiKey = String(process.env.WATCHDOG_WORKER_API_KEY || '').trim();

  const routes = {
    health: { method: 'GET', path: '/health', protected: false },
    capabilities: { method: 'GET', path: '/v1/capabilities', protected: true },
    triage: { method: 'POST', path: '/v1/triage/text', protected: true },
    crawl: { method: 'POST', path: '/v1/crawl/site', protected: true },
    osint: { method: 'POST', path: '/v1/osint/search', protected: true },
    torsearch: { method: 'POST', path: '/v1/tor/search', protected: true },
    torfetch: { method: 'POST', path: '/v1/tor/fetch', protected: true },
    ip: { method: 'POST', path: '/v1/intel/ip', protected: true },
    validate: { method: 'POST', path: '/v1/jobs/validate', protected: true },
    netprobe: { method: 'POST', path: '/v1/probe/network', protected: true },
    webprobe: { method: 'POST', path: '/v1/probe/web-security', protected: true },
  };

  const route = routes[action];
  if (!route) return json(res, 400, { error: 'Unknown worker action', allowed_actions: Object.keys(routes) });
  if (req.method !== route.method) {
    res.setHeader('Allow', route.method);
    return json(res, 405, { error: `Use ${route.method} for ${action}` });
  }
  if (route.protected && !apiKey) {
    return json(res, 503, { error: 'Worker bridge is not configured', detail: 'WATCHDOG_WORKER_API_KEY is missing from the Vercel environment.' });
  }

  let body;
  if (action === 'triage') {
    const text = typeof req.body?.text === 'string' ? req.body.text : '';
    if (!text || text.length > 200000) return json(res, 400, { error: 'text must contain 1 to 200000 characters' });
    body = { text };
  } else if (action === 'crawl') {
    const url = typeof req.body?.url === 'string' ? req.body.url.trim() : '';
    if (!url || url.length > 2048) return json(res, 400, { error: 'url is required and must be 2048 characters or fewer' });
    const maxPages = Number.isInteger(req.body?.max_pages) ? req.body.max_pages : 12;
    const maxDepth = Number.isInteger(req.body?.max_depth) ? req.body.max_depth : 1;
    if (maxPages < 1 || maxPages > 25 || maxDepth < 0 || maxDepth > 2) return json(res, 400, { error: 'max_pages must be 1-25 and max_depth must be 0-2' });
    body = { url, max_pages: maxPages, max_depth: maxDepth };
  } else if (action === 'osint') {
    const identifier = typeof req.body?.identifier === 'string' ? req.body.identifier.trim() : '';
    const kind = typeof req.body?.kind === 'string' ? req.body.kind.trim().toLowerCase() : 'name';
    const maxPerSource = Number.isInteger(req.body?.max_per_source) ? req.body.max_per_source : 6;
    if (!identifier || identifier.length > 320) return json(res, 400, { error: 'identifier is required and must be 320 characters or fewer' });
    if (maxPerSource < 1 || maxPerSource > 10) return json(res, 400, { error: 'max_per_source must be 1-10' });
    body = { identifier, kind, max_per_source: maxPerSource };
  } else if (action === 'torsearch') {
    const query = typeof req.body?.query === 'string' ? req.body.query.trim() : '';
    const maxResults = Number.isInteger(req.body?.max_results) ? req.body.max_results : 12;
    if (!query || query.length > 320) return json(res, 400, { error: 'query is required and must be 320 characters or fewer' });
    if (maxResults < 1 || maxResults > 25) return json(res, 400, { error: 'max_results must be 1-25' });
    body = { query, max_results: maxResults };
  } else if (action === 'torfetch') {
    const url = typeof req.body?.url === 'string' ? req.body.url.trim() : '';
    if (!url || url.length > 2048) return json(res, 400, { error: 'onion url is required and must be 2048 characters or fewer' });
    body = { url };
  } else if (action === 'ip') {
    const ip = typeof req.body?.ip === 'string' ? req.body.ip.trim() : '';
    if (!ip || ip.length > 64) return json(res, 400, { error: 'ip is required' });
    body = { ip };
  } else if (action === 'validate') {
    const jobType = typeof req.body?.job_type === 'string' ? req.body.job_type.trim() : '';
    if (!jobType || jobType.length > 100) return json(res, 400, { error: 'job_type is required' });
    body = {
      job_type: jobType,
      target: typeof req.body?.target === 'string' ? req.body.target.slice(0, 2048) : null,
      authorization_confirmed: req.body?.authorization_confirmed === true,
    };
  } else if (action === 'netprobe') {
    const target = typeof req.body?.target === 'string' ? req.body.target.trim() : '';
    const ports = Array.isArray(req.body?.ports) ? req.body.ports.map(Number).filter(Number.isInteger) : undefined;
    if (!target || target.length > 253) return json(res, 400, { error: 'target is required and must be 253 characters or fewer' });
    if (ports && (ports.length < 1 || ports.length > 20 || ports.some(p => p < 1 || p > 65535))) return json(res, 400, { error: 'ports must contain 1-20 integers between 1 and 65535' });
    body = { target, authorization_confirmed: req.body?.authorization_confirmed === true };
    if (ports) body.ports = ports;
  } else if (action === 'webprobe') {
    const url = typeof req.body?.url === 'string' ? req.body.url.trim() : '';
    if (!url || url.length > 2048) return json(res, 400, { error: 'url is required and must be 2048 characters or fewer' });
    body = { url, authorization_confirmed: req.body?.authorization_confirmed === true };
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 55000);
  try {
    const headers = { Accept: 'application/json' };
    if (route.protected) headers.Authorization = `Bearer ${apiKey}`;
    if (body) headers['Content-Type'] = 'application/json';
    const upstream = await fetch(`${workerUrl}${route.path}`, {
      method: route.method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      redirect: 'error',
    });
    return json(res, upstream.status, await readJsonResponse(upstream));
  } catch (error) {
    const timedOut = error?.name === 'AbortError';
    return json(res, timedOut ? 504 : 502, { error: timedOut ? 'Worker timed out while waking or processing the request' : 'Worker request failed' });
  } finally {
    clearTimeout(timeout);
  }
}
