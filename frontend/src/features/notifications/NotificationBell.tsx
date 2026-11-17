// Cloche de notifications : compteur de non lues (relevé toutes les 30 s), liste déroulante, lien vers l'objet concerné.
import { Bell } from 'lucide-react'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { formatDate } from '../../shared/lib/format'
import { cn } from '../../shared/lib/cn'
import { listNotifications, marquerLue, toutMarquerLu } from './api'
import type { Notification } from './api'

const key = ['notifications'] as const
const cible = (n: Notification) => n.reference_type === 'demande' ? '/demandes' : n.reference_type === 'document' ? null : null

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const nav = useNavigate()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: key, queryFn: listNotifications, refetchInterval: 30_000 })
  const refresh = () => qc.invalidateQueries({ queryKey: key })
  const lue = useMutation({ mutationFn: marquerLue, onSuccess: refresh })
  const toutes = useMutation({ mutationFn: toutMarquerLu, onSuccess: refresh })
  const n = q.data?.non_lues ?? 0
  const ouvrir = (x: Notification) => { if (!x.lu) lue.mutate(x.id); const to = cible(x); if (to) { setOpen(false); nav(to) } }
  return (
    <div className="relative">
      <button className="btn-icon relative" aria-label={`Notifications${n ? ` (${n} non lues)` : ''}`} onClick={() => setOpen((o) => !o)}>
        <Bell className="h-5 w-5" />
        {n > 0 && <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">{n > 99 ? '99+' : n}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 max-w-[90vw] rounded-lg border border-gold-500/30 bg-leaf-950 shadow-2xl">
          <div className="flex items-center justify-between border-b border-gold-500/20 px-3 py-2">
            <span className="text-sm font-semibold text-gold-300">Notifications</span>
            {n > 0 && <button className="text-xs text-cream-300 underline" onClick={() => toutes.mutate()}>Tout marquer comme lu</button>}
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {(q.data?.items ?? []).length === 0 && <li className="p-4 text-center text-sm text-cream-300">Rien de nouveau.</li>}
            {(q.data?.items ?? []).map((x) => (
              <li key={x.id}>
                <button className={cn('w-full px-3 py-2 text-left text-sm hover:bg-gold-500/10', !x.lu && 'bg-gold-500/5 font-medium')} onClick={() => ouvrir(x)}>
                  {x.message}<br /><span className="text-xs text-cream-300">{formatDate(x.cree_le)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
