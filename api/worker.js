const DEFAULT_PRIMARY_WORKER_URL = 'https://gpt6watchdog-2.onrender.com';
const DEFAULT_FALLBACK_WORKER_URL = 'https://worker-one-iota.vercel.app';

export const config = { maxDuration: 60 };

function json(res, status, body) {
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, private');
  res.setHeader('Pragma', 'no-cache');
  return res.status(status).json(body);
}

function cleanBaseUrl(value, fallback) {
  const raw = String(value || fallback).trim();
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:') return fallback;
    return url.origin;
  } catch {
    return fallback;
  }
}

async function readJsonResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); }
  catch { return { detail: text.slice(0, 4000) }; }
}

async function fetchWorker(baseUrl, route, body, apiKey, timeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = { Accept: 'application/json' };
    if (route.protected && apiKey) headers.Authorization = `Bearer ${apiKey}`;
    if (body) headers['Content-Type'] = 'application/json';

    const response = await fetch(`${baseUrl}${route.path}`, {
      method: route.method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      redirect: 'error',
    });

    return {
      ok: response.ok,
      status: response.status,
      data: await readJsonResponse(response),
      timedOut: false,
      networkError: false,
    };
  } catch (error) {
    return {
      ok: false,
      status: error?.name === 'AbortError' ? 504 : 502,
      data: {
        error: error?.name === 'AbortError'
          ? 'Worker timed out while waking or processing the request'
          : 'Worker request failed',
      },
      timedOut: error?.name === 'AbortError',
      networkError: true,
    };
  } finally {
    clearTimeout(timeout);
  }
}

function shouldFailOver(result) {
  return result.networkError || [500, 502, 503, 504].includes(result.status);
}

function backendSummary(result) {
  return {
    reachable: !result.networkError,
    status_code: result.status,
    status: result.data?.status || null,
    service: result.data?.service || null,
    version: result.data?.version || null,
    api_key_configured: typeof result.data?.api_key_configured === 'boolean'
      ? result.data.api_key_configured
      : null,
    tools: result.data?.tools || null,
  };
}

export default async function handler(req, res) {
  const action = String(req.query.action || '').trim().toLowerCase();
  const primaryUrl = cleanBaseUrl(process.env.WATCHDOG_WORKER_URL, DEFAULT_PRIMARY_WORKER_URL);
  const fallbackUrl = cleanBaseUrl(process.env.WATCHDOG_FALLBACK_WORKER_URL, DEFAULT_FALLBACK_WORKER_URL);
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

  if (action === 'health') {
    const [primary, fallback] = await Promise.all([
      fetchWorker(primaryUrl, route, null, '', 8000),
      primaryUrl === fallbackUrl
        ? Promise.resolve(null)
        : fetchWorker(fallbackUrl, route, null, '', 8000),
    ]);

    const primaryHealthy = primary?.ok && primary?.data?.status === 'ok';
    const fallbackHealthy = fallback?.ok && fallback?.data?.status === 'ok';
    const active = primaryHealthy ? 'primary' : (fallbackHealthy ? 'fallback' : 'none');
    const activeData = active === 'primary' ? primary.data : (active === 'fallback' ? fallback.data : {});

    return json(res, active === 'none' ? 503 : 200, {
      status: active === 'none' ? 'degraded' : 'ok',
      service: 'watchdog-worker-bridge',
      version: activeData?.version || null,
      active_backend: active,
      primary: backendSummary(primary),
      fallback: fallback ? backendSummary(fallback) : { same_as_primary: true },
      failover_enabled: primaryUrl !== fallbackUrl,
      note: fallbackHealthy && fallback?.data?.api_key_configured === false
        ? 'Fallback health is online, but protected failover actions require WATCHDOG_WORKER_API_KEY to also be configured on the fallback worker project.'
        : null,
    });
  }

  if (route.protected && !apiKey) {
    return json(res, 503, {
      error: 'Worker bridge is not configured',
      detail: 'WATCHDOG_WORKER_API_KEY is missing from the main Vercel environment.',
    });
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

  const primary = await fetchWorker(primaryUrl, route, body, apiKey, 32000);
  if (!shouldFailOver(primary) || primaryUrl === fallbackUrl) {
    return json(res, primary.status, {
      ...primary.data,
      _watchdog_backend: 'primary',
      _watchdog_failover_used: false,
    });
  }

  const fallback = await fetchWorker(fallbackUrl, route, body, apiKey, 20000);
  if (fallback.ok || !shouldFailOver(fallback)) {
    return json(res, fallback.status, {
      ...fallback.data,
      _watchdog_backend: 'fallback',
      _watchdog_failover_used: true,
      _watchdog_primary_status: primary.status,
    });
  }

  return json(res, fallback.status || primary.status || 502, {
    ...fallback.data,
    _watchdog_backend: 'fallback',
    _watchdog_failover_used: true,
    _watchdog_primary_status: primary.status,
    _watchdog_fallback_status: fallback.status,
    detail: fallback.data?.detail || fallback.data?.error || primary.data?.detail || primary.data?.error || 'Both worker backends failed',
  });
}
