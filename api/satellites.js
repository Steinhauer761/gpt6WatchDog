export const config = { maxDuration: 30 };

function json(res, status, body) {
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, private');
  return res.status(status).json(body);
}

function parseTle(text) {
  const lines = String(text || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  const out = [];
  for (let i = 0; i < lines.length - 2; ) {
    let name = lines[i];
    let l1 = lines[i + 1];
    let l2 = lines[i + 2];
    if (name.startsWith('1 ') && l1.startsWith('2 ')) {
      l2 = l1;
      l1 = name;
      name = `NORAD ${l1.slice(2, 7).trim()}`;
      i += 2;
    } else {
      if (name.startsWith('0 ')) name = name.slice(2).trim();
      i += 3;
    }
    if (!l1?.startsWith('1 ') || !l2?.startsWith('2 ')) continue;
    out.push({
      name: name.slice(0, 120),
      norad: l1.slice(2, 7).trim(),
      line1: l1,
      line2: l2,
    });
    if (out.length >= 25) break;
  }
  return out;
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return json(res, 405, { error: 'Use GET' });
  }

  const name = String(req.query.name || 'ISS').trim();
  if (!name || name.length > 80) return json(res, 400, { error: 'name is required and must be 80 characters or fewer' });

  const url = `https://celestrak.org/NORAD/elements/gp.php?NAME=${encodeURIComponent(name)}&FORMAT=TLE`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const r = await fetch(url, { headers: { 'User-Agent': 'WatchDog-Satellite-Map/0.3' }, signal: controller.signal, redirect: 'error' });
    if (!r.ok) return json(res, 502, { error: `CelesTrak returned HTTP ${r.status}` });
    const text = await r.text();
    const satellites = parseTle(text);
    return json(res, 200, {
      query: name,
      source: 'CelesTrak current GP data',
      count: satellites.length,
      satellites,
      note: 'Positions shown in the browser are propagated from public orbital element data and are estimates, not live imagery.',
    });
  } catch (error) {
    return json(res, error?.name === 'AbortError' ? 504 : 502, { error: error?.name === 'AbortError' ? 'Satellite lookup timed out' : 'Satellite lookup failed' });
  } finally {
    clearTimeout(timeout);
  }
}
