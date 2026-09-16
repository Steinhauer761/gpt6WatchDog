const VIN_RE = /^[A-HJ-NPR-Z0-9]{17}$/;
const FIELDS = ['Make', 'Model', 'ModelYear', 'Manufacturer', 'VehicleType', 'BodyClass', 'EngineCylinders', 'DisplacementL', 'FuelTypePrimary', 'DriveType', 'PlantCountry', 'ErrorCode', 'ErrorText'];

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'GET required' });
  }
  const vin = String(req.query.vin || '').trim().toUpperCase();
  if (!VIN_RE.test(vin)) return res.status(400).json({ error: 'Enter a 17-character VIN without I, O or Q.' });
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    let response;
    try {
      response = await fetch(`https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/${vin}?format=json`, { signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) throw new Error('Vehicle data service unavailable');
    const body = await response.json();
    const row = body.Results?.[0];
    if (!row) throw new Error('No vehicle record returned');
    return res.status(200).json({ vin, source: 'NHTSA vPIC', decoded: Object.fromEntries(FIELDS.map(key => [key, row[key] || null])) });
  } catch {
    return res.status(502).json({ error: 'The public VIN service did not respond. Try again later.' });
  }
}
