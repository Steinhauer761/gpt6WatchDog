export const config = { maxDuration: 20 };

function json(res, status, body) {
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, private');
  return res.status(status).json(body);
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return json(res, 405, { error: 'Use GET' });
  }

  const q = String(req.query.q || '').trim();
  if (!q || q.length > 180) return json(res, 400, { error: 'Enter an address or place name (180 characters max).' });

  const url = new URL('https://nominatim.openstreetmap.org/search');
  url.searchParams.set('q', q);
  url.searchParams.set('format', 'jsonv2');
  url.searchParams.set('addressdetails', '1');
  url.searchParams.set('limit', '5');
  url.searchParams.set('dedupe', '1');

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const r = await fetch(url, {
      headers: { 'User-Agent': 'WatchDog-Field-Tools/0.4 (address lookup)' },
      signal: controller.signal,
      redirect: 'error',
    });
    if (!r.ok) return json(res, 502, { error: `Geocoder returned HTTP ${r.status}` });

    const data = await r.json();
    const results = [];
    for (const item of Array.isArray(data) ? data : []) {
      const lat = Number(item.lat);
      const lon = Number(item.lon);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
      const a = item.address || {};
      results.push({
        label: item.display_name || q,
        latitude: lat,
        longitude: lon,
        type: item.addresstype || item.type || null,
        house_number: a.house_number || null,
        road: a.road || a.pedestrian || a.footway || null,
        neighbourhood: a.neighbourhood || a.suburb || null,
        city: a.city || a.town || a.village || a.municipality || null,
        region: a.state || a.region || a.county || null,
        postcode: a.postcode || null,
        country: a.country || null,
      });
      if (results.length >= 5) break;
    }

    return json(res, 200, {
      query: q,
      count: results.length,
      results,
      note: 'Address results come from public OpenStreetMap/Nominatim data. Verify important locations independently before relying on them.',
    });
  } catch (error) {
    return json(res, error?.name === 'AbortError' ? 504 : 502, {
      error: error?.name === 'AbortError' ? 'Address lookup timed out' : 'Address lookup failed',
    });
  } finally {
    clearTimeout(timer);
  }
}
