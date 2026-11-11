import axios from 'axios'

// This looks for the Vercel variable first; if missing, it falls back to local for dev
const API_BASE_URL = import.meta.env.VITE_API_URL?.replace(/\/+$/, '');

const client = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: false,
  withXSRFToken: false,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
  timeout: 60000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => {
    // Handle Rupee Roast style { success: true, data: ... }
    if (response.data && response.data.success === true && response.data.data !== undefined) {
      if (import.meta.env.DEV) {
        console.debug('[API OK]', response.config.method?.toUpperCase(), response.config.url, response.data.data)
      }
      return { ...response, data: response.data.data }
    }

    if (import.meta.env.DEV) {
      console.debug('[API OK]', response.config.method?.toUpperCase(), response.config.url, response.data)
    }
    return response
  },
  (error) => {
    const msg =
      error?.response?.data?.message ||
      error?.response?.data?.errors ||
      error.message ||
      'Request failed'

    if (error?.response?.status === 401) {
      localStorage.clear();
      const landingUrl = import.meta.env.VITE_LANDING_URL;
      if (landingUrl) {
        window.location.href = landingUrl;
      }
    }
    
    if (import.meta.env.DEV) {
      console.error('[API ERR]', error?.response?.status, error?.config?.url, msg)
    }
    return Promise.reject(error)
  }
)

export async function getCenters() {
  const { data } = await client.get('/centers')
  return data
}

export async function createCenter(payload) {
  const { data } = await client.post('/centers', payload)
  return data
}

export async function updateCenter(id, payload) {
  const { data } = await client.patch(`/centers/${id}`, payload)
  return data
}

export async function deleteCenter(id) {
  const { data } = await client.delete(`/centers/${id}`)
  return data
}

export async function getOrders(params = {}) {
  const { data } = await client.get('/orders', { params })
  return data
}

export async function getOrderDateCounts(year, month) {
  const { data } = await client.get('/orders/date-counts', { params: { year, month } })
  return data
}

export async function createOrder(payload) {
  const { data } = await client.post('/orders', payload)
  return data
}

export async function updateOrder(id, payload) {
  const { data } = await client.patch(`/orders/${id}`, payload)
  return data
}

export async function deleteOrder(id) {
  const { data } = await client.delete(`/orders/${id}`)
  return data
}

export async function clearOrdersByDate(date) {
  const { data } = await client.delete('/orders/clear-by-date', { params: { date } })
  return data
}

export async function getOrderBulkCounts(date) {
  const { data } = await client.get('/orders/bulk-counts', { params: { date } })
  return data
}

export async function deleteCompletedOrders(date) {
  const { data } = await client.delete('/orders/completed', { params: { date } })
  return data
}

export async function deletePendingOrders(date) {
  const { data } = await client.delete('/orders/pending', { params: { date } })
  return data
}

export async function deleteAllOrders(date) {
  const { data } = await client.delete('/orders', { params: { date } })
  return data
}

export async function markAllOrdersAsDelivered(date) {
  const { data } = await client.post('/orders/mark-all-delivered', { date })
  return data
}

export async function assignOrder(id) {
  const { data } = await client.post(`/orders/${id}/assign`)
  return data
}

export async function getVehicles(params = {}) {
  const { data } = await client.get('/vehicles', { params })
  return data
}

export async function createVehicle(payload) {
  const { data } = await client.post('/vehicles', payload)
  return data
}

export async function updateVehicle(id, payload) {
  const { data } = await client.patch(`/vehicles/${id}`, payload)
  return data
}

export async function resetFleet(payload = {}) {
  const { data } = await client.post('/vehicles/reset-fleet', payload)
  return data
}

export async function deleteVehicle(id) {
  const { data } = await client.delete(`/vehicles/${id}`)
  return data
}

export async function getZones() {
  const { data } = await client.get('/zones')
  return data
}

export async function saveZones(zones) {
  const { data } = await client.post('/zones/generate', { zones })
  return data
}

export async function generateRoute(payload = {}) {
  const { data } = await client.post('/routes/generate', payload)
  return data
}

export async function getRoutes() {
  const { data } = await client.get('/routes')
  return data
}

export async function getRoute(id) {
  const { data } = await client.get(`/routes/${id}`)
  return data
}

export async function regenerateRoutes(centerId, payload = {}) {
  const { data } = await client.post(`/routes/regenerate/${centerId}`, payload)
  return data
}

export async function clearRoutes(payload = {}) {
  const { data } = await client.delete('/routes/clear', { data: payload })
  return data
}


export { client }
