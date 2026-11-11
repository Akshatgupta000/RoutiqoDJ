export default function Card({ children, className = '', padding = true }) {
  return (
    <div
      className={`rounded-2xl border border-zinc-200 bg-white shadow-sm shadow-zinc-900/5 transition-shadow duration-200 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/40 ${padding ? 'p-5' : ''} ${className}`}
    >
      {children}
    </div>
  )
}
