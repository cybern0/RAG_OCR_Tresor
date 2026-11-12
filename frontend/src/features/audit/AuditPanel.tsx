// Journal d'audit en lecture seule : qui a fait quoi, et quand.
import { listAudit } from '../../api/structure'
import { ErrorBox, Loading } from '../../components/ui/Feedback'
import { useLoad } from '../../hooks/useLoad'

export default function AuditPanel() {
  const audit = useLoad(listAudit)
  if (audit.loading) return <Loading />
  return (
    <div className="space-y-3">
      <ErrorBox message={audit.error} />
      <div className="card overflow-x-auto">
        <table className="w-full border-collapse">
          <thead><tr><th className="th">Date</th><th className="th">Utilisateur</th><th className="th">Action</th><th className="th">Détail</th><th className="th">IP</th></tr></thead>
          <tbody>
            {(audit.data ?? []).map((r) => (
              <tr key={r.id}>
                <td className="td whitespace-nowrap text-xs text-cream-300">{new Date(r.cree_le).toLocaleString('fr-FR')}</td>
                <td className="td text-sm">{r.nom_utilisateur ?? '—'}</td>
                <td className="td text-sm font-medium text-gold-300">{r.action}</td>
                <td className="td max-w-sm break-words text-xs text-cream-300">{r.entite ? `${r.entite} #${r.entite_id ?? ''} ` : ''}{Object.keys(r.detail).length ? JSON.stringify(r.detail) : ''}</td>
                <td className="td text-xs text-cream-300">{r.adresse_ip ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
