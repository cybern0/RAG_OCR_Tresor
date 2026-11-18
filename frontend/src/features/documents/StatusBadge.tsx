// Pastille de statut d'indexation d'une version.
import type { Statut } from './types'

const STATUS: Record<Statut, { label: string; cls: string }> = {
  pending: { label: 'En attente', cls: 'border-cream-300/60 text-cream-100' },
  processing: { label: 'Indexation…', cls: 'border-gold-400 bg-gold-500/15 text-gold-300' },
  ready: { label: 'Prêt', cls: 'border-emerald-300/70 bg-emerald-400/15 text-emerald-100' },
  error: { label: 'Erreur', cls: 'border-red-300/70 bg-red-400/15 text-red-100' },
}

export function StatusBadge({ statut }: { statut: Statut }) {
  return <span className={`badge ${STATUS[statut].cls}`}>{STATUS[statut].label}</span>
}
