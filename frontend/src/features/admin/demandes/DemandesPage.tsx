// Demandes d'accès à un dossier ou à un fichier : en attente en haut ; accepter (avec le rôle accordé) ou refuser.
import { Inbox } from 'lucide-react'
import { useState } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { formatDate } from '../../../shared/lib/format'
import Badge from '../../../shared/ui/Badge'
import { EmptyState, ErrorBox, Loading } from '../../../shared/ui/Feedback'
import PageHeader from '../../../shared/ui/PageHeader'
import { useToast } from '../../../shared/hooks/useToast'
import { ROLES_DOSSIER, roleLabel } from '../../dossiers/types'
import { decideAccessRequest } from '../api'
import { adminKeys, useAccessRequests, useAdminMutation } from '../queries'
import type { AccessRequest } from '../types'

const STATUS = { pending: ['En attente', 'amber'], accepted: ['Acceptée', 'green'], rejected: ['Refusée', 'red'] } as const

function Row({ r }: { r: AccessRequest }) {
  const toast = useToast()
  const [role, setRole] = useState(r.requested_role)
  const decide = useAdminMutation((v: { decision: 'accepted' | 'rejected' }) => decideAccessRequest(r.id!, v.decision, role), [adminKeys.demandes])
  const [label, tone] = STATUS[r.status as keyof typeof STATUS] ?? [r.status, 'gray' as const]
  const run = (decision: 'accepted' | 'rejected') => decide.mutateAsync({ decision }).then(() => toast.success(decision === 'accepted' ? 'Demande acceptée.' : 'Demande refusée.')).catch((e) => toast.error(errorMessage(e)))
  return (
    <tr className="hover:bg-slate-50">
      <td className="td"><span className="font-medium">{r.requester_name ?? `Utilisateur ${r.requested_by}`}</span><br /><span className="text-xs text-slate-600">{formatDate(r.created_at)}</span></td>
      <td className="td">{r.subject_type === 'dossier' ? 'Dossier' : 'Fichier'} · <span className="text-navy-600">{r.subject_name ?? `#${r.subject_id}`}</span></td>
      <td className="td max-w-xs text-sm text-slate-600">{r.message || '—'}</td>
      <td className="td">
        {r.status === 'pending' ? (
          <select className="input w-auto" aria-label="Rôle accordé" value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES_DOSSIER.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
          </select>
        ) : roleLabel(r.requested_role)}
      </td>
      <td className="td"><Badge tone={tone}>{label}</Badge></td>
      <td className="td">
        {r.status === 'pending' && (
          <div className="flex justify-end gap-1">
            <button className="btn" disabled={decide.isPending} onClick={() => void run('accepted')}>Accepter</button>
            <button className="btn-danger" disabled={decide.isPending} onClick={() => void run('rejected')}>Refuser</button>
          </div>
        )}
      </td>
    </tr>
  )
}

export function Component() {
  const [filter, setFilter] = useState<'pending' | 'all'>('pending')
  const requests = useAccessRequests(filter === 'pending' ? 'pending' : undefined)
  return (
    <>
      <PageHeader title="Demandes d’accès" description="Examiner les demandes d’accès des utilisateurs à un dossier ou à un fichier."
        actions={(
          <div className="flex gap-1 rounded-lg border border-line p-0.5">
            {(['pending', 'all'] as const).map((f) => (
              <button key={f} className={`rounded-md px-3 py-1 text-sm ${filter === f ? 'bg-navy-700 font-semibold text-white' : 'text-black hover:bg-navy-100'}`} onClick={() => setFilter(f)}>{f === 'pending' ? 'En attente' : 'Toutes'}</button>
            ))}
          </div>
        )} />
      <ErrorBox message={requests.error ? errorMessage(requests.error) : null} />
      {requests.isPending ? <Loading /> : (requests.data ?? []).length === 0 ? (
        <EmptyState icon={<Inbox className="h-8 w-8" />} title={filter === 'pending' ? 'Aucune demande en attente' : 'Aucune demande'} />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead><tr><th className="th">Demandeur</th><th className="th">Sujet</th><th className="th">Message</th><th className="th">Rôle</th><th className="th">Statut</th><th className="th" /></tr></thead>
            <tbody>{requests.data!.map((r) => <Row key={r.id} r={r} />)}</tbody>
          </table>
        </div>
      )}
    </>
  )
}
