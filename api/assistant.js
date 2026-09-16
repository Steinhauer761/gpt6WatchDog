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
    return url.protocol === 'https:' ? url.origin : DEFAULT_WORKER_URL;
  } catch {
    return DEFAULT_WORKER_URL;
  }
}

async function workerCall(action, payload) {
  const workerUrl = cleanBaseUrl(process.env.WATCHDOG_WORKER_URL);
  const key = String(process.env.WATCHDOG_WORKER_API_KEY || '').trim();
  if (!key) return { error: 'WatchDog worker key is not configured in Vercel.' };
  const routes = {
    lookup_ip: '/v1/intel/ip',
    public_search: '/v1/osint/search',
    tor_search: '/v1/tor/search',
    crawl_site: '/v1/crawl/site',
    triage_text: '/v1/triage/text',
  };
  const path = routes[action];
  if (!path) return { error: 'Unsupported tool action.' };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45000);
  try {
    const r = await fetch(`${workerUrl}${path}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload || {}),
      signal: controller.signal,
      redirect: 'error',
    });
    const text = await r.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text.slice(0, 4000) }; }
    if (!r.ok) return { error: data.detail || data.error || `Worker returned HTTP ${r.status}` };
    return data;
  } catch (error) {
    return { error: error?.name === 'AbortError' ? 'Worker timed out.' : 'Worker request failed.' };
  } finally {
    clearTimeout(timer);
  }
}

async function runTool(name, args) {
  if (name === 'lookup_ip') return workerCall(name, { ip: String(args.ip || '').trim() });
  if (name === 'public_search') return workerCall(name, {
    identifier: String(args.identifier || '').trim(),
    kind: String(args.kind || 'name').trim().toLowerCase(),
    max_per_source: Math.max(1, Math.min(Number(args.max_per_source) || 6, 10)),
  });
  if (name === 'tor_search') return workerCall(name, {
    query: String(args.query || '').trim(),
    max_results: Math.max(1, Math.min(Number(args.max_results) || 12, 25)),
  });
  if (name === 'crawl_site') return workerCall(name, {
    url: String(args.url || '').trim(),
    max_pages: Math.max(1, Math.min(Number(args.max_pages) || 8, 20)),
    max_depth: Math.max(0, Math.min(Number(args.max_depth) || 1, 2)),
  });
  if (name === 'triage_text') return workerCall(name, { text: String(args.text || '').slice(0, 50000) });
  return { error: 'Unknown tool.' };
}

function extractText(response) {
  if (typeof response?.output_text === 'string' && response.output_text.trim()) return response.output_text.trim();
  const chunks = [];
  for (const item of response?.output || []) {
    if (item?.type !== 'message') continue;
    for (const part of item.content || []) {
      if (part?.type === 'output_text' && typeof part.text === 'string') chunks.push(part.text);
    }
  }
  return chunks.join('\n').trim();
}

const tools = [
  {
    type: 'function',
    name: 'lookup_ip',
    description: 'Look up approximate network geolocation and ASN/organization for a public IP address. This is not precise person tracking.',
    parameters: { type: 'object', properties: { ip: { type: 'string' } }, required: ['ip'], additionalProperties: false },
    strict: true,
  },
  {
    type: 'function',
    name: 'public_search',
    description: 'Search multiple lawful public sources for a name, username, alias, email, phone number or domain. Results are leads, not proof of identity.',
    parameters: {
      type: 'object',
      properties: {
        identifier: { type: 'string' },
        kind: { type: 'string', enum: ['name', 'username', 'alias', 'email', 'phone', 'domain'] },
        max_per_source: { type: 'integer', minimum: 1, maximum: 10 },
      },
      required: ['identifier', 'kind', 'max_per_source'],
      additionalProperties: false,
    },
    strict: true,
  },
  {
    type: 'function',
    name: 'tor_search',
    description: 'Search Ahmia public Tor index for lawful public onion-service references. Do not use for illicit purchasing, stolen credentials or private-account access.',
    parameters: {
      type: 'object',
      properties: { query: { type: 'string' }, max_results: { type: 'integer', minimum: 1, maximum: 25 } },
      required: ['query', 'max_results'], additionalProperties: false,
    },
    strict: true,
  },
  {
    type: 'function',
    name: 'crawl_site',
    description: 'Crawl a public website with strict page/depth limits and private-network blocking.',
    parameters: {
      type: 'object',
      properties: {
        url: { type: 'string' }, max_pages: { type: 'integer', minimum: 1, maximum: 20 }, max_depth: { type: 'integer', minimum: 0, maximum: 2 },
      },
      required: ['url', 'max_pages', 'max_depth'], additionalProperties: false,
    },
    strict: true,
  },
  {
    type: 'function',
    name: 'triage_text',
    description: 'Extract URLs, emails and IPv4 indicators from supplied text and hash the evidence.',
    parameters: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'], additionalProperties: false },
    strict: true,
  },
];

const instructions = `You are WatchDog Assistant inside a private defensive OSINT/security console. Be concise and practical. You may use the provided passive tools. Treat all public-source identity matches as leads, not proof. IP geolocation is approximate network metadata, not a person's exact location. Never claim to track a person in real time, reveal or infer a private home address, access private accounts, retrieve passwords, bypass logins/firewalls, hack back, or launch active penetration tests from chat. If the user asks for active security testing, direct them to the separately authorized dashboard workflow. Tor research is passive and limited to public onion-service references; do not facilitate illegal marketplaces, stolen data, credential trafficking or evasion of law enforcement. For mapping a named person, only use clearly public city/country-level clues with source and uncertainty; do not map residential addresses.`;

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return json(res, 405, { error: 'Use POST' });
  }

  const apiKey = String(process.env.OPENAI_API_KEY || '').trim();
  if (!apiKey) return json(res, 503, { error: 'AI assistant is not configured yet', detail: 'OPENAI_API_KEY is missing from the Vercel environment.' });

  const message = typeof req.body?.message === 'string' ? req.body.message.trim() : '';
  if (!message || message.length > 12000) return json(res, 400, { error: 'message must contain 1 to 12000 characters' });
  const history = Array.isArray(req.body?.history) ? req.body.history.slice(-8) : [];
  const input = [];
  for (const item of history) {
    const role = item?.role === 'assistant' ? 'assistant' : 'user';
    const content = typeof item?.content === 'string' ? item.content.slice(0, 6000) : '';
    if (content) input.push({ role, content });
  }
  input.push({ role: 'user', content: message });

  const model = String(process.env.OPENAI_MODEL || 'gpt-5.6-luna').trim();
  let response;
  try {
    const r = await fetch('https://api.openai.com/v1/responses', {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, instructions, input, tools, store: false, reasoning: { effort: 'low' } }),
    });
    response = await r.json();
    if (!r.ok) return json(res, r.status, { error: response?.error?.message || 'OpenAI request failed' });

    for (let round = 0; round < 3; round += 1) {
      const calls = (response.output || []).filter(x => x?.type === 'function_call');
      if (!calls.length) break;
      const outputs = [];
      for (const call of calls) {
        let args = {};
        try { args = JSON.parse(call.arguments || '{}'); } catch { args = {}; }
        const result = await runTool(call.name, args);
        outputs.push({ type: 'function_call_output', call_id: call.call_id, output: JSON.stringify(result) });
      }
      const follow = await fetch('https://api.openai.com/v1/responses', {
        method: 'POST',
        headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, previous_response_id: response.id, input: outputs, tools, store: false }),
      });
      response = await follow.json();
      if (!follow.ok) return json(res, follow.status, { error: response?.error?.message || 'OpenAI tool follow-up failed' });
    }

    const text = extractText(response) || 'I completed the request, but no text response was returned.';
    return json(res, 200, { reply: text, model });
  } catch (error) {
    return json(res, 502, { error: 'AI assistant request failed' });
  }
}
