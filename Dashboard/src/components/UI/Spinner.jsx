export default function Spinner({ className = 'h-8 w-8' }) {
  return (
    <div
      className={`inline-block animate-spin rounded-full border-2 border-solid border-emerald-500 border-r-transparent ${className}`}
      role="status"
      aria-label="Loading"
    />
  )
}
