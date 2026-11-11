import { getDistance } from './coords'

export function kmhToMps(kmh) {
  const n = Number(kmh)
  if (!Number.isFinite(n) || n <= 0) return null
  return (n * 1000) / 3600
}

export function segmentLengthMeters(a, b) {
  if (!a || !b) return 0
  const km = getDistance(a[0], a[1], b[0], b[1])
  const m = km * 1000
  return Number.isFinite(m) ? m : 0
}

export function lerpLatLng(a, b, t) {
  const tt = Math.max(0, Math.min(1, t))
  return [a[0] + (b[0] - a[0]) * tt, a[1] + (b[1] - a[1]) * tt]
}

function toRad(deg) {
  return (deg * Math.PI) / 180
}

function toDeg(rad) {
  return (rad * 180) / Math.PI
}

/**
 * Bearing in degrees (0=N, 90=E).
 * Uses great-circle initial bearing.
 */
export function getBearingDegrees(a, b) {
  if (!a || !b) return 0
  const lat1 = toRad(a[0])
  const lat2 = toRad(b[0])
  const dLng = toRad(b[1] - a[1])
  const y = Math.sin(dLng) * Math.cos(lat2)
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng)
  const brng = toDeg(Math.atan2(y, x))
  const norm = (brng + 360) % 360
  return Number.isFinite(norm) ? norm : 0
}

