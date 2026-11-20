// Pastille de statut d'indexation d'une version.
import type { Statut } from './types'

const STATUS: Record<Statut, { label: string; cls: string }> = {
  pending: { label: 'En attente', cls: 'border-slate-300 text-black' },
  processing: { label: 'Indexation…', cls: 'border-navy-600 bg-navy-100 text-navy-600' },
  ready: { label: 'Prêt', cls: 'border-emerald-300 bg-emerald-50 text-emerald-800' },
  error: { label: 'Erreur', cls: 'border-red-300 bg-red-50 text-red-800' },
}

export function StatusBadge({ statut }: { statut: Statut }) {
  return <span className={`badge ${STATUS[statut].cls}`}>{STATUS[statut].label}</span>
}
