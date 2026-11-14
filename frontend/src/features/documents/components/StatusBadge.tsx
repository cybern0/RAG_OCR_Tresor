import { CheckCircle2, Clock, Loader2, XCircle } from 'lucide-react'
import Badge from '../../../shared/ui/Badge'
import type { Statut } from '../types'

const STATUS = {
  pending: { label: 'En attente', tone: 'gray', icon: Clock },
  processing: { label: 'Indexation…', tone: 'gold', icon: Loader2 },
  ready: { label: 'Prêt', tone: 'green', icon: CheckCircle2 },
  error: { label: 'Erreur', tone: 'red', icon: XCircle },
} as const

export function StatusBadge({ statut }: { statut: Statut }) {
  const { label, tone, icon: Icon } = STATUS[statut]
  return <Badge tone={tone}><Icon className={`h-3 w-3 ${statut === 'processing' ? 'animate-spin' : ''}`} aria-hidden /> {label}</Badge>
}
