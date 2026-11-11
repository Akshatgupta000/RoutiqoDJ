import { stopLatLng } from './coords'
import { extractRouteCoordinates } from './routeGeometry'

/**
 * Path for map playback: prefer OSRM polyline; otherwise hub → stops (dense straight segments).
 * @returns {Array<[number, number]>}
 */
export function buildPlaybackPathForRoute(route, centers = []) {
  if (!route) return []

  const poly = extractRouteCoordinates(route)
  const isStarted = route.status === 'in_progress'
  
  // If route is started, we MUST use dynamic path to start from current vehicle position.
  // Otherwise, prefer OSRM polyline for static/planned routes.
  if (!isStarted && poly.length >= 2) return poly

  const center =
    route.delivery_center ||
    centers.find((c) => String(c.id) === String(route.delivery_center_id))
  const hub = stopLatLng(center)

  const nextSeq = route.next_stop_sequence ?? 1
  
  // Starting point: hub if planned, current vehicle position if in progress
  const startPos = isStarted && route.vehicle?.latitude 
    ? [route.vehicle.latitude, route.vehicle.longitude] 
    : hub

  const stops = [...(route.stops ?? [])]
    .sort((a, b) => a.sequence - b.sequence)
    .filter(s => s.sequence >= nextSeq) // Only include remaining stops

  /** @type {Array<[number, number]>} */
  const anchors = []

  if (Number.isFinite(startPos[0]) && Number.isFinite(startPos[1]) && !(startPos[0] === 0 && startPos[1] === 0)) {
    anchors.push(startPos)
  }

  for (const s of stops) {
    const p = stopLatLng(s)
    if (!Number.isFinite(p[0]) || !Number.isFinite(p[1])) continue
    if (p[0] === 0 && p[1] === 0) continue
    anchors.push(p)
  }

  // Return to hub at the end
  if (anchors.length > 0 && Number.isFinite(hub[0]) && Number.isFinite(hub[1])) {
    anchors.push(hub)
  }

  if (anchors.length < 2) return []

  /** Densify segments so “Simulate movement” visibly steps along the route. */
  /** @type {Array<[number, number]>} */
  const dense = []
  const perSegment = 10
  for (let i = 0; i < anchors.length - 1; i++) {
    const a = anchors[i]
    const b = anchors[i + 1]
    for (let s = 0; s < perSegment; s++) {
      const t = s / perSegment
      dense.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t])
    }
  }
  dense.push(anchors[anchors.length - 1])

  return dense.length >= 2 ? dense : []
}

/**
 * Build path for a single leg of the route.
 */
export function buildLegPath(route, centers = []) {
  if (!route) return []
  
  const center =
    route.delivery_center ||
    centers.find((c) => String(c.id) === String(route.delivery_center_id))
  const hub = stopLatLng(center)
  const stops = [...(route.stops ?? [])].sort((a, b) => a.sequence - b.sequence)
  
  const nextSeq = route.next_stop_sequence ?? 1
  
  let startPos, endPos
  
  if (route.status === 'planned') {
    // Leg: Hub -> Stop 1
    startPos = hub
    endPos = stops.length > 0 ? stopLatLng(stops[0]) : hub
  } else if (route.status === 'in_progress') {
    if (nextSeq === 1) {
      // Still moving to first stop
      startPos = hub
      endPos = stops.length > 0 ? stopLatLng(stops[0]) : hub
    } else {
      // Moving from prev stop to next stop
      const prevStop = stops.find(s => s.sequence === nextSeq - 1)
      const nextStop = stops.find(s => s.sequence === nextSeq)
      startPos = prevStop ? stopLatLng(prevStop) : hub
      endPos = nextStop ? stopLatLng(nextStop) : hub
    }
  } else if (route.status === 'completed') {
    // Leg: Last stop -> Hub
    const lastStop = stops[stops.length - 1]
    startPos = lastStop ? stopLatLng(lastStop) : hub
    endPos = hub
  } else {
    return []
  }

  // Densify the single segment
  const dense = []
  const perSegment = 30 // Higher density for single leg to look smoother
  for (let s = 0; s < perSegment; s++) {
    const t = s / perSegment
    dense.push([startPos[0] + (endPos[0] - startPos[0]) * t, startPos[1] + (endPos[1] - startPos[1]) * t])
  }
  dense.push(endPos)
  
  return dense
}
