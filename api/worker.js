const DEFAULT_WORKER_URL = 'https://gpt6watchdog-2.onrender.com';

export const config = {
  maxDuration: 60,
};

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
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text.slice(0, 4000) };
  }
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
    validate: { method: 'POST', path: '/v1/jobs/validate', protected: true },
  };

  const route = routes[action];
  if (!route) {
    return json(res, 400, {
      error: 'Unknown worker action',
      allowed_actions: Object.keys(routes),
    });
  }

  if (req.method !== route.method) {
    res.setHeader('Allow', route.method);
    return json(res, 405, { error: `Use ${route.method} for ${action}` });
  }

  if (route.protected && !apiKey) {
    return json(res, 503, {
      error: 'Worker bridge is not configured',
      detail: 'WATCHDOG_WORKER_API_KEY is missing from the Vercel environment.',
    });
  }

  let body;
  if (action === 'triage') {
    const text = typeof req.body?.text === 'string' ? req.body.text : '';
    if (!text || text.length > 200000) {
      return json(res, 400, { error: 'text must contain 1 to 200000 characters' });
    }
    body = { text };
  } else if (action === 'crawl') {
    const url = typeof req.body?.url === 'string' ? req.body.url.trim() : '';
    if (!url || url.length > 2048) {
      return json(res, 400, { error: 'url is required and must be 2048 characters or fewer' });
    }
    const maxPages = Number.isInteger(req.body?.max_pages) ? req.body.max_pages : 12;
    const maxDepth = Number.isInteger(req.body?.max_depth) ? req.body.max_depth : 1;
    if (maxPages < 1 || maxPages > 25 || maxDepth < 0 || maxDepth > 2) {
      return json(res, 400, { error: 'max_pages must be 1-25 and max_depth must be 0-2' });
    }
    body = { url, max_pages: maxPages, max_depth: maxDepth };
  } else if (action === 'validate') {
    const jobType = typeof req.body?.job_type === 'string' ? req.body.job_type.trim() : '';
    if (!jobType || jobType.length > 100) {
      return json(res, 400, { error: 'job_type is required' });
    }
    body = {
      job_type: jobType,
      target: typeof req.body?.target === 'string' ? req.body.target.slice(0, 2048) : null,
      authorization_confirmed: req.body?.authorization_confirmed === true,
    };
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

    const payload = await readJsonResponse(upstream);
    return json(res, upstream.status, payload);
  } catch (error) {
    const timedOut = error?.name === 'AbortError';
    return json(res, timedOut ? 504 : 502, {
      error: timedOut ? 'Worker timed out while waking or processing the request' : 'Worker request failed',
    });
  } finally {
    clearTimeout(timeout);
  }
}
