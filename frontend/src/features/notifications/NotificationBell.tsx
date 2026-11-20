// Cloche de notifications : compteur de non lues (relevé toutes les 30 s), liste déroulante, lien vers l'objet concerné,
// « tout marquer comme lu » et « nettoyer » (les lues et les demandes déjà tranchées ou annulées).
import { Bell } from 'lucide-react'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { errorMessage } from '../../shared/api/client'
import { formatDate } from '../../shared/lib/format'
import { cn } from '../../shared/lib/cn'
import { useToast } from '../../shared/hooks/useToast'
import { listNotifications, marquerLue, nettoyerNotifications, toutMarquerLu } from './api'
import type { Notification } from './api'

const key = ['notifications'] as const
const cible = (n: Notification) => { if (n.reference_type === 'document') return null; return null }

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const nav = useNavigate()
  const toast = useToast()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: key, queryFn: listNotifications, refetchInterval: 30_000 })
  const refresh = () => qc.invalidateQueries({ queryKey: key })
  const lue = useMutation({ mutationFn: marquerLue, onSuccess: refresh })
  const toutes = useMutation({ mutationFn: toutMarquerLu, onSuccess: refresh })
  const nettoyer = useMutation({
    mutationFn: nettoyerNotifications,
    onSuccess: (r) => { refresh(); toast.success(`Nettoyage : ${r.supprimees} notification(s) supprimée(s).`) },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const n = q.data?.non_lues ?? 0
  const ouvrir = (x: Notification) => { if (!x.lu) lue.mutate(x.id); const to = cible(x); if (to) { setOpen(false); nav(to) } }
  return (
    <div className="relative">
      <button className="btn-icon relative" aria-label={`Notifications${n ? ` (${n} non lues)` : ''}`} onClick={() => setOpen((o) => !o)}>
        <Bell className="h-5 w-5" />
        {n > 0 && <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">{n > 99 ? '99+' : n}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 max-w-[90vw] rounded-lg border border-line bg-white text-black shadow-float">
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <span className="text-sm font-semibold text-navy-600">Notifications</span>
            <div className="flex items-center gap-3">
              {n > 0 && <button className="text-xs text-slate-600 underline" onClick={() => toutes.mutate()}>Tout marquer comme lu</button>}
              {(q.data?.items ?? []).length > 0 && (
                <button className="text-xs text-slate-600 underline" title="Supprime les notifications lues et celles des demandes déjà tranchées ou annulées"
                  onClick={() => nettoyer.mutate()}>
                  Nettoyer
                </button>
              )}
            </div>
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {(q.data?.items ?? []).length === 0 && <li className="p-4 text-center text-sm text-slate-600">Rien de nouveau.</li>}
            {(q.data?.items ?? []).map((x) => (
              <li key={x.id}>
                <button className={cn('w-full px-3 py-2 text-left text-sm hover:bg-navy-50', !x.lu && 'bg-navy-50 font-medium')} onClick={() => ouvrir(x)}>
                  {x.message}<br /><span className="text-xs text-slate-600">{formatDate(x.cree_le)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
