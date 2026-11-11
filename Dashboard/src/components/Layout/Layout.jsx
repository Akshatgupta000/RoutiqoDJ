import { useEffect, useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import Sidebar from '../Sidebar/Sidebar'
import ToastContainer from '../UI/ToastContainer'
import { useApp } from '../../context/AppContext'

export default function Layout() {
  const { toasts, dismissToast, bootstrapError } = useApp()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const tokenParam = params.get('token')
    const userParam = params.get('user')

    if (tokenParam) {
      localStorage.setItem('auth_token', tokenParam)
      if (userParam) {
        localStorage.setItem('user', decodeURIComponent(userParam))
      }
      window.history.replaceState({}, document.title, window.location.pathname)
      window.location.reload()
      return
    }

    const token = localStorage.getItem('auth_token')
    if (!token) {
      window.location.href = import.meta.env.VITE_LANDING_URL || 'http://localhost:5173'
    }
  }, [])

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-zinc-100 text-zinc-900 md:flex-row dark:bg-zinc-950 dark:text-zinc-100">
      {/* Mobile Header */}
      <header className="flex h-14 w-full shrink-0 items-center justify-between border-b border-zinc-200 bg-white px-4 md:hidden dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex flex-col">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-500 leading-none mb-1">
            Last-Mile
          </p>
          <h1 className="text-2xl font-bold tracking-tight leading-none">Routiqo</h1>
        </div>
        <button
          onClick={() => setSidebarOpen(true)}
          className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
        >
          <Menu className="h-6 w-6" />
        </button>
      </header>

      {/* Sidebar Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-zinc-900/50 backdrop-blur-sm transition-opacity md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar - Drawer on Mobile, Compact on Tablet, Full on Desktop */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-zinc-200 bg-zinc-50/95 transition-transform duration-300 ease-in-out md:relative md:translate-x-0 md:border-zinc-200/90 dark:border-zinc-800 dark:bg-zinc-950/95 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } md:w-20 lg:w-72`}
      >
        <div className="absolute right-4 top-4 md:hidden">
          <button
            onClick={() => setSidebarOpen(false)}
            className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
          >
            <X className="h-6 w-6" />
          </button>
        </div>
        <Sidebar onClose={() => setSidebarOpen(false)} isCollapsed={true} />
      </aside>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {bootstrapError && (
          <div
            className="border-b border-red-200 bg-red-50 px-4 py-2 text-center text-sm text-red-900 dark:border-red-900 dark:bg-red-950/80 dark:text-red-100"
            role="alert"
          >
            {bootstrapError}
          </div>
        )}
        <main className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          <Outlet />
        </main>
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
