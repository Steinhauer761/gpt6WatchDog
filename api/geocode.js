export const config = { maxDuration: 20 };

function json(res, status, body) {
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, private');
  return res.status(status).json(body);
}

const ALLOWED_TYPES = new Set(['city', 'town', 'village', 'municipality', 'state', 'country', 'county', 'administrative']);

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return json(res, 405, { error: 'Use GET' });
  }

  const q = String(req.query.q || '').trim();
  if (!q || q.length > 120) return json(res, 400, { error: 'Enter a city, region or country (120 characters max).' });
  if (/\d/.test(q)) return json(res, 400, { error: 'Street addresses are not accepted. Use a public city, region or country clue only.' });
  if (!/^[\p{L}\s,.'()\-]+$/u.test(q)) return json(res, 400, { error: 'Use a city, region or country name only.' });

  const url = new URL('https://nominatim.openstreetmap.org/search');
  url.searchParams.set('q', q);
  url.searchParams.set('format', 'jsonv2');
  url.searchParams.set('addressdetails', '1');
  url.searchParams.set('limit', '5');

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const r = await fetch(url, {
      headers: { 'User-Agent': 'WatchDog-Field-Tools/0.3 (coarse public-place mapping)' },
      signal: controller.signal,
      redirect: 'error',
    });
    if (!r.ok) return json(res, 502, { error: `Geocoder returned HTTP ${r.status}` });
    const data = await r.json();
    const results = [];
    for (const item of Array.isArray(data) ? data : []) {
      const type = String(item.addresstype || item.type || '').toLowerCase();
      if (!ALLOWED_TYPES.has(type)) continue;
      const a = item.address || {};
      const city = a.city || a.town || a.village || a.municipality || a.county || null;
      const region = a.state || a.region || a.county || null;
      const country = a.country || null;
      const lat = Number(item.lat), lon = Number(item.lon);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
      const label = [...new Set([city, region, country].filter(Boolean))].join(', ') || q;
      results.push({ label, city, region, country, latitude: Math.round(lat * 100) / 100, longitude: Math.round(lon * 100) / 100, type });
      if (results.length >= 3) break;
    }
    return json(res, 200, {
      query: q,
      count: results.length,
      results,
      note: 'Coarse public-place mapping only. Street-level and residential-address mapping is intentionally excluded.',
    });
  } catch (error) {
    return json(res, error?.name === 'AbortError' ? 504 : 502, { error: error?.name === 'AbortError' ? 'Geocoder timed out' : 'Geocoder request failed' });
  } finally {
    clearTimeout(timer);
  }
}
