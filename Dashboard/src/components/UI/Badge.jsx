const styles = {
  pending:
    'bg-amber-100 text-amber-900 dark:bg-amber-500/20 dark:text-amber-200',
  assigned:
    'bg-sky-100 text-sky-900 dark:bg-sky-500/20 dark:text-sky-200',
  delivered:
    'bg-emerald-100 text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200',
  planned:
    'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200',
  in_progress:
    'bg-violet-100 text-violet-900 dark:bg-violet-500/20 dark:text-violet-200',
  completed:
    'bg-emerald-100 text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-200',
  priority:
    'bg-red-500 text-white',
  normal:
    'bg-gray-200 text-zinc-900 dark:bg-zinc-700 dark:text-zinc-200',
  default:
    'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
}

export default function Badge({ children, status }) {
  const key = status?.toLowerCase?.() || 'default'
  const cls = styles[key] || styles.default

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${cls}`}
    >
      {children}
    </span>
  )
}
