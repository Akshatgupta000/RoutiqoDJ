import { useEffect, useState } from 'react'
import Modal from '../UI/Modal'
import Button from '../UI/Button'
import { useApp } from '../../context/AppContext'

export default function AddVehicleModal({ open, onClose, centers, toast, initialCenterId }) {
  const { addVehicleAction } = useApp()
  const [form, setForm] = useState({
    name: '',
    capacity: 6,
    average_speed: 30,
    is_available: true,
    delivery_center_id: initialCenterId || centers[0]?.id || '',
  })

  useEffect(() => {
    if (initialCenterId) {
      setForm(f => ({ ...f, delivery_center_id: initialCenterId }))
    }
  }, [initialCenterId])

  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await addVehicleAction({
        name: form.name,
        capacity: Number(form.capacity),
        average_speed: Number(form.average_speed),
        is_available: form.is_available,
        delivery_center_id: form.delivery_center_id,
      })
      onClose?.()
      setForm({
        name: '',
        capacity: 6,
        average_speed: 30,
        is_available: true,
        delivery_center_id: centers[0]?.id || '',
      })
    } catch (err) {
      // toast is handled in action
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add vehicle"
      footer={
        <>
          <Button variant="ghost" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="add-vehicle-form" disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </>
      }
    >
      <form id="add-vehicle-form" className="space-y-4" onSubmit={submit}>
        <div>
          <label className="mb-1 block text-xs font-semibold text-zinc-600 dark:text-zinc-400">
            Name
          </label>
          <input
            required
            autoFocus
            className="w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold text-zinc-600 dark:text-zinc-400">
            Delivery center
          </label>
          <select
            required
            className="w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            value={form.delivery_center_id}
            onChange={(e) =>
              setForm((f) => ({ ...f, delivery_center_id: e.target.value }))
            }
          >
            {centers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-semibold text-zinc-600 dark:text-zinc-400">
              Capacity (stops)
            </label>
            <input
              required
              type="number"
              min={1}
              className="w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.capacity}
              onChange={(e) => setForm((f) => ({ ...f, capacity: e.target.value }))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-zinc-600 dark:text-zinc-400">
              Avg speed (km/h)
            </label>
            <input
              required
              type="number"
              min={1}
              className="w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={form.average_speed}
              onChange={(e) => setForm((f) => ({ ...f, average_speed: e.target.value }))}
            />
          </div>
        </div>
        <label className="flex items-center gap-3 text-sm cursor-pointer select-none">
          <div className="relative">
            <input
              type="checkbox"
              checked={form.is_available}
              onChange={(e) => setForm((f) => ({ ...f, is_available: e.target.checked }))}
              className="sr-only peer"
            />
            <div className="w-10 h-5 bg-zinc-300 rounded-full peer-checked:bg-emerald-500 transition-colors dark:bg-zinc-600" />
            <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-5" />
          </div>
          <span className={form.is_available ? 'text-emerald-600 font-semibold' : 'text-red-500 font-semibold'}>
            {form.is_available ? 'Available for routing' : 'Unavailable'}
          </span>
        </label>
      </form>
    </Modal>
  )
}
