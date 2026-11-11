export default function Table({ columns, rows, empty }) {
  if (!rows?.length) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-300 py-12 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
        {empty || 'No records'}
      </div>
    )
  }

  return (
    <div className="overflow-visible rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
      <div className="overflow-x-auto overflow-y-visible custom-scrollbar">
        <table className="w-full text-left text-sm md:table block">
          <thead className="bg-zinc-50/50 dark:bg-zinc-900/50 md:table-header-group hidden">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="whitespace-nowrap px-6 py-4 font-black uppercase tracking-widest text-[10px] text-zinc-500"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800 md:table-row-group block">
            {rows.map((row, i) => (
              <tr
                key={row.id ?? i}
                className="transition-all hover:bg-zinc-50/50 dark:hover:bg-zinc-900/30 md:table-row block group relative hover:z-50"
              >
                {columns.map((col) => (
                  <td 
                    key={col.key} 
                    className="px-6 py-4 md:table-cell block relative"
                  >
                    <div className="flex md:flex-col items-center justify-between md:items-start gap-2">
                      <span className="md:hidden text-[10px] font-black uppercase tracking-widest text-zinc-400">
                        {col.label}
                      </span>
                      <div className="text-zinc-900 dark:text-white font-medium">
                        {col.render ? col.render(row) : row[col.key]}
                      </div>
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
