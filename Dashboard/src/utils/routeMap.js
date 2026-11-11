import { stopLatLng, stopPoint } from './coords'

function lerp(a, b, t) {
  return {
    lat: a.lat + (b.lat - a.lat) * t,
    lng: a.lng + (b.lng - a.lng) * t,
  }
}

export function computeVehiclePosition(route) {
  if (!route?.delivery_center) return null
  const c = route.delivery_center
  const depot = { lat: Number(c.latitude), lng: Number(c.longitude) }
  const stops = [...(route.stops || [])].sort((a, b) => a.sequence - b.sequence)

  if (!stops.length) return depot

  if (route.status === 'planned') {
    return depot
  }

  if (route.status === 'completed') {
    const last = stops[stops.length - 1]
    const pt = stopPoint(last)
    return { lat: pt.lat, lng: pt.lng }
  }

  const k = route.next_stop_sequence
  if (k == null) return depot

  if (k === 1) {
    const [lat, lng] = stopLatLng(stops[0])
    const first = { lat, lng }
    return lerp(depot, first, 0.42)
  }

  const prev = stops.find((s) => s.sequence === k - 1)
  if (prev) {
    const pt = stopPoint(prev)
    return { lat: pt.lat, lng: pt.lng }
  }

  return depot
}
