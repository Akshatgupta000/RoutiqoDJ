/**
 * Normalize backend route geometry: supports geometry | coordinates as [[lat,lng], ...].
 */

function pairFromArray(p) {
  if (!Array.isArray(p) || p.length < 2) return null
  const lat = Number(p[0])
  const lng = Number(p[1])
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  return [lat, lng]
}

export function extractRouteCoordinates(route) {
  if (!route || typeof route !== 'object') return []
  const raw = route.geometry ?? route.coordinates
  if (Array.isArray(raw) && raw.length >= 2) {
    const out = []
    for (let i = 0; i < raw.length; i++) {
      const pair = pairFromArray(raw[i])
      if (pair) out.push(pair)
    }
    if (out.length >= 2) return out;
  }
  
  // Fallback: draw straight lines between stops
  const coords = [];
  if (route.delivery_center || route.deliveryCenter) {
    const depot = route.delivery_center || route.deliveryCenter;
    if (depot.latitude && depot.longitude) {
       coords.push([Number(depot.latitude), Number(depot.longitude)]);
    }
  }

  if (route.stops && route.stops.length > 0) {
    const sortedStops = [...route.stops].sort((a,b) => a.sequence - b.sequence);
    sortedStops.forEach(stop => {
       const lat = stop.latitude ?? stop.lat;
       const lng = stop.longitude ?? stop.lng;
       if (lat && lng) {
           coords.push([Number(lat), Number(lng)]);
       }
    });
  }

  if (route.delivery_center || route.deliveryCenter) {
    const depot = route.delivery_center || route.deliveryCenter;
    if (depot.latitude && depot.longitude) {
       coords.push([Number(depot.latitude), Number(depot.longitude)]);
    }
  }

  return coords.length >= 2 ? coords : [];
}
