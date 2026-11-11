/**
 * Normalize stop coordinates from API (latitude/longitude) or legacy (lat/lng).
 */
export function stopLatLng(stop) {
  if (!stop) return [0, 0]
  const lat = Number(stop.latitude ?? stop.lat ?? 0)
  const lng = Number(stop.longitude ?? stop.lng ?? 0)
  return [Number.isFinite(lat) ? lat : 0, Number.isFinite(lng) ? lng : 0]
}

export function stopPoint(stop) {
  const [lat, lng] = stopLatLng(stop)
  return { lat, lng }
}

/**
 * Calculate Haversine distance in km between two points
 */
export function getDistance(lat1, lon1, lat2, lon2) {
  const R = 6371 // Earth's radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2)

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}
