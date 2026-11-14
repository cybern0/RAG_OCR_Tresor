import { ChevronLeft, ChevronRight } from 'lucide-react'

export default function Pagination({ page, taille, total, onPage }: { page: number; taille: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / taille))
  if (total <= taille) return null
  return (
    <nav className="flex items-center justify-between gap-3 px-1 pt-3 text-sm text-cream-300" aria-label="Pagination">
      <span>{(page - 1) * taille + 1}–{Math.min(page * taille, total)} sur {total}</span>
      <div className="flex items-center gap-1">
        <button className="btn-icon" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Page précédente"><ChevronLeft className="h-4 w-4" /></button>
        <span className="px-2">{page} / {pages}</span>
        <button className="btn-icon" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Page suivante"><ChevronRight className="h-4 w-4" /></button>
      </div>
    </nav>
  )
}
