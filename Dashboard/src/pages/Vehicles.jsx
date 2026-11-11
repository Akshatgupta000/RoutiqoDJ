import { useState } from 'react'
import Button from '../components/UI/Button'
import Table from '../components/UI/Table'
import Badge from '../components/UI/Badge'
import AddVehicleModal from '../components/Forms/AddVehicleModal'
import EditVehicleModal from '../components/Forms/EditVehicleModal'
import * as api from '../services/api'
import { useApp } from '../context/AppContext'
import Modal from '../components/UI/Modal'

export default function Vehicles() {
  const { 
    vehicles, 
    refreshVehicles, 
    toast, 
    centers, 
    resetFleetAction, 
    loading, 
    toggleVehicleAvailability,
    resetSelection,
    generateRoutesAction
  } = useApp()
  const [modal, setModal] = useState(false)
  const [editVehicle, setEditVehicle] = useState(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const columns = [
    {
      key: 'vehicle_number',
      label: 'Reg. No.',
      render: (r) => (
        <span className="font-mono text-xs font-bold tracking-wider text-zinc-800 dark:text-zinc-200">
          {r.vehicle_number || '—'}
        </span>
      ),
    },
    { key: 'name', label: 'Name' },
    { key: 'capacity', label: 'Capacity' },
    {
      key: 'speed',
      label: 'Avg km/h',
      render: (r) => r.average_speed ?? '—',
    },
    {
      key: 'avail',
      label: 'Status',
      render: (r) => (
        <div className="flex items-center">
          <button 
            onClick={() => toggleVehicleAvailability(r.id, r.is_available)}
            className="group flex items-center gap-2.5 outline-none"
            title={r.is_available ? "Mark as Busy" : "Mark as Available"}
          >
            <div className="relative">
              <div className={`w-8 h-4 rounded-full transition-colors ${r.is_available ? 'bg-emerald-500' : 'bg-zinc-300 dark:bg-zinc-700'}`} />
              <div className={`absolute top-0.5 w-3 h-3 bg-white rounded-full transition-transform ${r.is_available ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
            </div>
            <span className={`text-[10px] font-bold uppercase tracking-wider transition-colors ${r.is_available ? 'text-emerald-600 dark:text-emerald-400' : 'text-zinc-400'}`}>
              {r.is_available ? 'Available' : 'Busy'}
            </span>
          </button>
        </div>
      ),
    },
    {
      key: 'center',
      label: 'Center',
      render: (r) => r.delivery_center?.name ?? (r.delivery_center_id ? `#${r.delivery_center_id}` : 'Not Assigned'),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (r) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => setEditVehicle(r)}
            className="flex items-center gap-1 rounded-lg bg-blue-50 px-2.5 py-1.5 text-xs font-semibold text-blue-600 hover:bg-blue-100 transition-colors dark:bg-blue-950/40 dark:text-blue-400 dark:hover:bg-blue-950/60"
            title="Edit vehicle"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Edit
          </button>
          <button
            onClick={() => setDeleteConfirmId(r.id)}
            className="flex items-center gap-1 rounded-lg bg-red-50 px-2.5 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-100 transition-colors dark:bg-red-950/40 dark:text-red-400 dark:hover:bg-red-950/60"
            title="Delete vehicle"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Delete
          </button>
        </div>
      ),
    },
  ]

  return (
    <div className="flex h-full flex-col overflow-auto p-4 lg:p-8">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl lg:text-3xl font-black tracking-tight text-zinc-900 dark:text-white">
            Vehicles
          </h1>
          <p className="text-sm font-medium text-zinc-500">Fleet capacity and availability.</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <Button variant="secondary" onClick={() => resetFleetAction()} disabled={loading.resetFleet} className="w-full sm:w-auto">
            {loading.resetFleet ? 'Resetting...' : 'Reset Fleet Status'}
          </Button>
          <Button onClick={() => setModal(true)} className="w-full sm:w-auto shadow-lg">
            Add vehicle
          </Button>
        </div>
      </div>

      <Table columns={columns} rows={vehicles} empty="No vehicles." />

      <AddVehicleModal
        open={modal}
        onClose={() => setModal(false)}
        centers={centers}
        toast={toast}
        onCreated={refreshVehicles}
      />

      <EditVehicleModal
        open={!!editVehicle}
        onClose={() => setEditVehicle(null)}
        vehicle={editVehicle}
        centers={centers}
        toast={toast}
        onUpdated={refreshVehicles}
      />

      <Modal
        open={!!deleteConfirmId}
        onClose={() => setDeleteConfirmId(null)}
        title="Delete Vehicle?"
        footer={
          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => setDeleteConfirmId(null)}>Cancel</Button>
            <Button 
              variant="danger" 
              disabled={isDeleting}
              onClick={async () => {
                setIsDeleting(true)
                try {
                  await api.deleteVehicle(deleteConfirmId)
                  toast('Vehicle deleted. Synchronizing map...')
                  resetSelection()
                  await refreshVehicles()
                  await generateRoutesAction()
                  setDeleteConfirmId(null)
                } catch (err) {
                  toast('Failed to delete vehicle.', 'error')
                } finally {
                  setIsDeleting(false)
                }
              }}
            >
              {isDeleting ? 'Deleting...' : 'Delete Vehicle'}
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Are you sure you want to delete this vehicle? This action will:
          </p>
          <ul className="list-disc pl-5 text-xs space-y-1 text-zinc-500 dark:text-zinc-400">
            <li>Permanently remove the vehicle from your fleet</li>
            <li>Reset current map selections</li>
            <li>Automatically regenerate delivery routes for the affected area</li>
          </ul>
        </div>
      </Modal>
    </div>
  )
}
