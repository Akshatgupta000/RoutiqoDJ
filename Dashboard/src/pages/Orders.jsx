import { useEffect, useState, useMemo } from 'react'
import Button from '../components/UI/Button'
import Card from '../components/UI/Card'
import Table from '../components/UI/Table'
import Badge from '../components/UI/Badge'
import Skeleton from '../components/UI/Skeleton'
import AddOrderModal from '../components/Forms/AddOrderModal'
import { useApp } from '../context/AppContext'
import * as api from '../services/api'
import AddCenterModal from '../components/Forms/AddCenterModal'
import AddVehicleModal from '../components/Forms/AddVehicleModal'
import { formatId, getLocalDateString } from '../utils/format'
import Modal from '../components/UI/Modal'
import { PRIORITIES } from '../utils/constants'

import CleanupOrders from '../components/Orders/CleanupOrders'

export default function Orders() {
  const { 
    centers, 
    orders, 
    setOrders,
    vehicles, 
    refreshOrders, 
    refreshRoutes, 
    refreshVehicles, 
    toast, 
    selectedDate, 
    activeMultiRoutes,
    orderFilters,
    setOrderFilters,
    addActivityLog
  } = useApp()

  const [pageLoading, setPageLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [deleteConfirmId, setDeleteConfirmId] = useState(null)
  const [showMarkAllConfirm, setShowMarkAllConfirm] = useState(false)
  const [bulkLoading, setBulkLoading] = useState(false)
  
  // Suggestion states
  const [centerSuggestion, setCenterSuggestion] = useState(null)
  const [vehicleSuggestion, setVehicleSuggestion] = useState(null)
  const [isCleanupOpen, setIsCleanupOpen] = useState(false)

  const filteredOrders = useMemo(() => {
    return orders.filter(o => {
      const matchHub = !orderFilters.hub || String(o.delivery_center_id) === String(orderFilters.hub)
      const matchStatus = !orderFilters.status || o.status === orderFilters.status
      return matchHub && matchStatus
    })
  }, [orders, orderFilters])

  useEffect(() => {
    // Silently refresh in background without blocking the UI
    refreshOrders()
  }, [refreshOrders])

  const columns = [
    { key: 'id', label: 'ID', render: (r) => `#${formatId(r.id)}` },
    { key: 'address', label: 'Address' },
    { key: 'delivery_date', label: 'Date', render: (r) => r.delivery_date || '—' },
    {
      key: 'priority',
      label: 'Priority',
      render: (r) => {
        const togglePriority = async () => {
          const newPriority = r.priority === 'priority' ? 'normal' : 'priority'
          
          // Optimistic update
          setOrders(prev => prev.map(o => String(o.id) === String(r.id) ? { ...o, priority: newPriority } : o))
          
          try {
            await api.updateOrder(r.id, { priority: newPriority })
            toast(`Priority set to ${newPriority}`)
            addActivityLog('Order Priority', `Priority for order at "${r.address}" was changed to ${newPriority}.`, 'info')
            refreshOrders()
            refreshRoutes()
          } catch (err) {
            // Rollback on error
            setOrders(prev => prev.map(o => String(o.id) === String(r.id) ? { ...o, priority: r.priority } : o))
            toast('Failed to update priority', 'error')
          }
        }

        return (
          <div 
            onClick={togglePriority}
            className="relative inline-block transition-all duration-200 hover:scale-110 active:scale-95 cursor-pointer hover:shadow-md hover:shadow-primary/10 rounded-full"
            title={`Click to toggle: ${r.priority === 'priority' ? 'Normal' : 'High Priority'}`}
          >
            <Badge status={r.priority}>{r.priority}</Badge>
          </div>
        )
      },
    },
    {
      key: 'status',
      label: 'Status',
      render: (r) => {
        const liveAssignment = activeMultiRoutes.find(route => route.stops?.some(s => String(s.order_id) === String(r.id)))
        const displayStatus = r.status === 'delivered' ? 'delivered' : (liveAssignment ? 'assigned' : r.status)
        return <Badge status={displayStatus}>{displayStatus}</Badge>
      },
    },
    {
      key: 'center',
      label: 'Center',
      render: (r) => r.delivery_center?.name ?? `#${r.delivery_center_id}`,
    },
    {
      key: 'vehicle',
      label: 'Vehicle',
      render: (r) => {
        // Check for live assignment from routing plan first
        const liveRoute = activeMultiRoutes.find(route => route.stops?.some(s => String(s.order_id) === String(r.id)))
        const liveVehicle = liveRoute ? vehicles.find(v => String(v.id) === String(liveRoute.vehicle_id)) : null
        
        const effectiveVehicle = liveVehicle || r.vehicle
        const isLive = !!liveVehicle

        const orderCenterId = String(r.delivery_center?.id ?? r.delivery_center_id ?? '')
        const centerVehicles = vehicles.filter(v => {
          const vCenterId = String(v.delivery_center?.id ?? v.delivery_center_id ?? '')
          return vCenterId === orderCenterId && v.is_available
        })
        const firstAvailable = centerVehicles[0]

        const handleChange = async (vid) => {
          if (!vid) return
          setOrders(prev => prev.map(o => String(o.id) === String(r.id) ? { ...o, vehicle_id: vid, status: 'assigned' } : o))
          try {
            await api.updateOrder(r.id, { vehicle_id: vid, status: 'assigned' })
            toast('Vehicle assigned successfully')
            const v = vehicles.find(v => String(v.id) === String(vid))
            const vName = v ? v.name || v.vehicle_number : vid;
            addActivityLog('Order Assigned', `Order at "${r.address}" was manually assigned to vehicle driver "${vName}".`, 'success')
            refreshVehicles()
          } catch (err) {
            refreshOrders()
            toast('Assignment failed', 'error')
          }
        }

        return (
          <div className="group relative min-w-[140px]">
            {!effectiveVehicle ? (
              <div className="flex flex-col py-1">
                <span className="text-[9px] font-black uppercase tracking-tighter text-zinc-400">
                  Assignment
                </span>
                <span className="text-xs font-bold text-zinc-400 dark:text-zinc-500">
                  Not Assigned
                </span>
              </div>
            ) : (
              <div className="flex flex-col py-1">
                <div className="flex items-center gap-1.5">
                  <span className={`text-[9px] font-black uppercase tracking-tighter ${isLive ? 'text-indigo-500' : 'text-zinc-400'}`}>
                    {isLive ? 'In Plan' : 'Assigned'}
                  </span>
                  {isLive && (
                    <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
                  )}
                </div>
                <span className={`text-xs font-bold ${isLive ? 'text-indigo-600 dark:text-indigo-400' : 'text-zinc-900 dark:text-white'}`}>
                  {effectiveVehicle.name}
                </span>
                {effectiveVehicle.vehicle_number && (
                  <span className="font-mono text-[9px] text-zinc-400">
                    {effectiveVehicle.vehicle_number}
                  </span>
                )}
              </div>
            )}

            {centerVehicles.length > 0 && (
              <select
                className="absolute inset-0 cursor-pointer opacity-0"
                value={effectiveVehicle?.id || ''}
                onChange={(e) => handleChange(e.target.value)}
              >
                <option value="" disabled>
                  {effectiveVehicle ? 'Change vehicle...' : 'Assign to...'}
                </option>
                {centerVehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.vehicle_number})
                  </option>
                ))}
              </select>
            )}
          </div>
        )
      },
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (r) => (
        <div className="flex items-center gap-3">
          {r.status === 'pending' && (
            <button
              onClick={() => handleAssign(r.id)}
              className="text-emerald-500 hover:text-emerald-700 transition-colors"
              title="Assign order to nearest center/vehicle"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
              </svg>
            </button>
          )}
          {r.status === 'assigned' && (
            <button
              onClick={() => handleDeliver(r.id)}
              className="text-blue-500 hover:text-blue-700 transition-colors"
              title="Mark as Delivered"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </button>
          )}
          <button
            onClick={() => handleDelete(r.id)}
            className="text-red-500 hover:text-red-700 transition-colors"
            title="Delete order"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      ),
    },
  ]

  const handleAssign = async (id) => {
    setOrders(prev => prev.map(o => String(o.id) === String(id) ? { ...o, status: 'assigned' } : o))
    try {
      const res = await api.assignOrder(id)
      const updatedOrder = res.data || res
      setOrders(prev => prev.map(o => String(o.id) === String(id) ? updatedOrder : o))
      toast('Order assigned successfully')
      const targetOrder = orders.find(o => String(o.id) === String(id));
      const addr = targetOrder ? targetOrder.address : `Order #${formatId(id)}`;
      addActivityLog('Order Assigned', `Order at "${addr}" was auto-assigned to a vehicle.`, 'success')
      refreshVehicles()
    } catch (err) {
      refreshOrders()
      const errorData = err?.response?.data?.errors || {}
      
      // Check for structured suggestions
      const addressErr = errorData.address?.[0]
      const vehicleErr = errorData.vehicle_id?.[0]

      if (addressErr?.code === 'no_center') {
        if (window.confirm(`${addressErr.message} \n\nWould you like to create a new delivery center at this location?`)) {
          setCenterSuggestion({
            lat: addressErr.lat,
            lng: addressErr.lng,
            address: 'New suggested center'
          })
        }
      } else if (vehicleErr?.code === 'no_vehicle') {
        if (window.confirm(`${vehicleErr.message} \n\nWould you like to add a new vehicle to this center?`)) {
          setVehicleSuggestion({
            center_id: vehicleErr.center_id
          })
        }
      } else {
        const msg = err?.response?.data?.message || 'Failed to assign order'
        toast(msg, 'error')
      }
    }
  }

  const handleDeliver = async (id) => {
    setOrders(prev => prev.map(o => String(o.id) === String(id) ? { ...o, status: 'delivered' } : o))
    try {
      await api.updateOrder(id, { status: 'delivered' })
      toast('Order marked as delivered')
      const targetOrder = orders.find(o => String(o.id) === String(id));
      const addr = targetOrder ? targetOrder.address : `Order #${formatId(id)}`;
      addActivityLog('Order Delivered', `Order at "${addr}" was marked as delivered.`, 'success')
      refreshRoutes()
      refreshVehicles()
    } catch (err) {
      refreshOrders()
      toast('Failed to update status', 'error')
    }
  }

  const handleDelete = (id) => {
    setDeleteConfirmId(id)
  }

  const confirmDelete = async () => {
    if (!deleteConfirmId) return
    const id = deleteConfirmId
    setOrders(prev => prev.filter(o => String(o.id) !== String(id)))
    setDeleteConfirmId(null)
    try {
      await api.deleteOrder(id)
      toast('Order deleted')
      const targetOrder = orders.find(o => String(o.id) === String(id));
      const addr = targetOrder ? targetOrder.address : `Order #${formatId(id)}`;
      addActivityLog('Order Deleted', `Order at "${addr}" was deleted.`, 'info')
    } catch (err) {
      refreshOrders()
      toast('Failed to delete order', 'error')
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden p-4 lg:p-8">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl lg:text-3xl font-black tracking-tight text-zinc-900 dark:text-white">
            Orders
          </h1>
          <p className="text-sm font-medium text-zinc-500">Create and track delivery requests.</p>
        </div>
        {selectedDate >= getLocalDateString() && (
          <Button onClick={() => setModal(true)} className="w-full sm:w-auto shadow-lg">
            Add new order
          </Button>
        )}
      </div>

      <Card className="mb-6 p-4 lg:p-6 bg-white/50 backdrop-blur-sm dark:bg-zinc-900/50 border-zinc-200/60 dark:border-zinc-800/60">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:flex lg:items-end lg:gap-6">
            <div className="flex flex-col gap-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-zinc-400">Delivery Hub</label>
              <div className="relative min-w-[220px]">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-zinc-400">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <select
                  className="w-full rounded-xl border border-zinc-200 bg-white py-2.5 pl-10 pr-3 text-sm font-bold text-zinc-900 transition-all hover:border-zinc-300 focus:border-primary focus:ring-4 focus:ring-primary/10 dark:border-zinc-800 dark:bg-zinc-950 dark:text-white"
                  value={orderFilters.hub}
                  onChange={(e) => setOrderFilters(prev => ({ ...prev, hub: e.target.value }))}
                >
                  <option value="">All Delivery Hubs</option>
                  {centers.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-zinc-400">Status</label>
              <div className="relative min-w-[180px]">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-zinc-400">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <select
                  className="w-full rounded-xl border border-zinc-200 bg-white py-2.5 pl-10 pr-3 text-sm font-bold text-zinc-900 transition-all hover:border-zinc-300 focus:border-primary focus:ring-4 focus:ring-primary/10 dark:border-zinc-800 dark:bg-zinc-950 dark:text-white"
                  value={orderFilters.status}
                  onChange={(e) => setOrderFilters(prev => ({ ...prev, status: e.target.value }))}
                >
                  <option value="">All Statuses</option>
                  <option value="pending">Pending</option>
                  <option value="assigned">Assigned</option>
                  <option value="delivered">Delivered</option>
                </select>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-zinc-400">Delivery date</label>
              <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm font-bold text-zinc-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-300">
                <svg className="h-4 w-4 shrink-0 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <span className="truncate">
                  {new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })}
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-3 border-t border-zinc-100 pt-4 lg:border-none lg:pt-0">
            <button
              onClick={() => setShowMarkAllConfirm(true)}
              disabled={orders.length === 0}
              className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-xs font-black uppercase tracking-wider text-blue-700 shadow-sm transition-all hover:bg-blue-100 active:scale-95 disabled:opacity-50 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-400"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Mark All Delivered</span>
            </button>
            <div className="w-full sm:w-auto">
              <CleanupOrders 
                onOpenChange={setIsCleanupOpen}
                onActionComplete={() => {
                  refreshOrders()
                  refreshRoutes()
                }} 
                toast={toast} 
              />
            </div>
          </div>
        </div>
      </Card>

      <div className={`flex-1 overflow-auto min-h-0 transition-all duration-300 ${isCleanupOpen ? 'pointer-events-none opacity-40 blur-[2px] grayscale-[0.5]' : ''}`}>
        {pageLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <Table columns={columns} rows={filteredOrders} empty="No orders match the selected filters." />
        )}
      </div>

      <AddOrderModal
        open={modal}
        onClose={() => setModal(false)}
        toast={toast}
        onCreated={() => refreshOrders()}
      />

      <AddCenterModal
        open={!!centerSuggestion}
        onClose={() => setCenterSuggestion(null)}
        initialData={centerSuggestion}
      />

      <AddVehicleModal
        open={!!vehicleSuggestion}
        onClose={() => setVehicleSuggestion(null)}
        centers={centers}
        toast={toast}
        initialCenterId={vehicleSuggestion?.center_id}
        onCreated={() => refreshOrders()}
      />

      <Modal
        open={!!deleteConfirmId}
        onClose={() => setDeleteConfirmId(null)}
        title="Delete Order?"
        footer={
          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => setDeleteConfirmId(null)}>Cancel</Button>
            <Button variant="danger" onClick={confirmDelete}>Delete</Button>
          </div>
        }
      >
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Are you sure you want to delete this order? This action cannot be undone.
        </p>
      </Modal>

      <Modal
        open={showMarkAllConfirm}
        onClose={() => setShowMarkAllConfirm(false)}
        title="Mark All Orders as Delivered?"
        footer={
          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => setShowMarkAllConfirm(false)}>Cancel</Button>
            <Button 
              variant="primary" 
              disabled={bulkLoading}
              onClick={async () => {
                setBulkLoading(true)
                setOrders(prev => prev.map(o => o.status !== 'delivered' ? { ...o, status: 'delivered' } : o))
                try {
                  const res = await api.markAllOrdersAsDelivered(selectedDate)
                  toast(`Success: ${res.updated_count} orders marked as delivered`)
                  addActivityLog('Bulk Delivery Update', `${res.updated_count} orders for ${selectedDate} were marked as delivered.`, 'success')
                  refreshRoutes()
                  refreshVehicles()
                  setShowMarkAllConfirm(false)
                } catch (err) {
                  refreshOrders()
                  toast('Failed to mark all as delivered', 'error')
                } finally {
                  setBulkLoading(false)
                }
              }}
            >
              {bulkLoading ? 'Updating...' : 'Confirm Bulk Update'}
            </Button>
          </div>
        }
      >
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          This will update the status of all <span className="font-semibold text-zinc-900 dark:text-white">pending</span> and <span className="font-semibold text-zinc-900 dark:text-white">assigned</span> orders for <span className="font-bold">{new Date(selectedDate + 'T00:00:00').toLocaleDateString()}</span> to <span className="font-semibold text-zinc-900 dark:text-white">delivered</span>.
        </p>
      </Modal>
    </div>
  )
}
