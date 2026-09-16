export const config = { maxDuration: 20 };

function json(res, status, body) {
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, private');
  return res.status(status).json(body);
}

function cleanText(value, max = 180) {
  return String(value || '').replace(/[\u0000-\u001f\u007f]/g, ' ').trim().slice(0, max);
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return json(res, 405, { error: 'Use GET' });
  }

  const q = cleanText(req.query.q);
  if (!q) return json(res, 400, { error: 'Enter an address, landmark, business, city, region or country.' });

  const url = new URL('https://nominatim.openstreetmap.org/search');
  url.searchParams.set('q', q);
  url.searchParams.set('format', 'jsonv2');
  url.searchParams.set('addressdetails', '1');
  url.searchParams.set('limit', '6');

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const r = await fetch(url, {
      headers: {
        'User-Agent': 'WatchDog-Field-Tools/0.4 (+https://gpt6-watch-dog.vercel.app)',
        'Accept-Language': 'en',
      },
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
      const houseNumber = cleanText(a.house_number, 40) || null;
      const road = cleanText(a.road || a.pedestrian || a.footway, 120) || null;
      const city = cleanText(a.city || a.town || a.village || a.municipality || a.hamlet, 120) || null;
      const region = cleanText(a.state || a.region || a.county, 120) || null;
      const country = cleanText(a.country, 120) || null;
      const postalCode = cleanText(a.postcode, 32) || null;
      const displayName = cleanText(item.display_name, 500) || q;
      const label = displayName;
      const latitude = Math.round(lat * 1e6) / 1e6;
      const longitude = Math.round(lon * 1e6) / 1e6;
      const coord = `${latitude},${longitude}`;

      results.push({
        label,
        display_name: displayName,
        house_number: houseNumber,
        road,
        city,
        region,
        country,
        postal_code: postalCode,
        latitude,
        longitude,
        type: cleanText(item.addresstype || item.type, 80) || 'place',
        maps_url: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(coord)}`,
        street_view_url: `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${encodeURIComponent(coord)}`,
        osm_url: `https://www.openstreetmap.org/?mlat=${encodeURIComponent(latitude)}&mlon=${encodeURIComponent(longitude)}#map=18/${encodeURIComponent(latitude)}/${encodeURIComponent(longitude)}`,
      });
    }

    return json(res, 200, {
      query: q,
      count: results.length,
      results,
      note: 'Address and place search uses public map data. Street View opens Google Maps at the returned coordinates when imagery is available. Do not treat a map result as proof that a person lives at an address.',
    });
  } catch (error) {
    const timedOut = error?.name === 'AbortError';
    return json(res, timedOut ? 504 : 502, { error: timedOut ? 'Geocoder timed out' : 'Geocoder request failed' });
  } finally {
    clearTimeout(timer);
  }
}
