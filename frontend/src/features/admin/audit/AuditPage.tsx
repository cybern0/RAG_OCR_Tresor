import { errorMessage } from '../../../shared/api/client'
import { formatDate } from '../../../shared/lib/format'
import { EmptyState, ErrorBox, Loading } from '../../../shared/ui/Feedback'
import PageHeader from '../../../shared/ui/PageHeader'
import { useAudit } from '../queries'

export function Component() {
  const audit = useAudit()
  return (
    <>
      <PageHeader title="Journal d’audit" description="Les 200 actions les plus récentes : connexions, accès, modifications, suppressions." />
      <ErrorBox message={audit.error ? errorMessage(audit.error) : null} />
      {audit.isPending ? <Loading /> : (audit.data ?? []).length === 0 ? <EmptyState title="Journal vide" /> : (
        <div className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead><tr><th className="th">Date</th><th className="th">Utilisateur</th><th className="th">Action</th><th className="th">Objet</th><th className="th">Détail</th><th className="th">IP</th></tr></thead>
            <tbody>
              {audit.data!.map((r) => (
                <tr key={r.id} className="hover:bg-leaf-700/40">
                  <td className="td whitespace-nowrap text-xs">{formatDate(r.cree_le)}</td>
                  <td className="td">{r.nom_utilisateur ?? '—'}</td>
                  <td className="td font-mono text-xs text-gold-300">{r.action}</td>
                  <td className="td text-xs">{r.entite ? `${r.entite} #${r.entite_id ?? ''}` : '—'}</td>
                  <td className="td max-w-xs truncate font-mono text-xs text-cream-300" title={JSON.stringify(r.detail)}>{Object.keys(r.detail).length ? JSON.stringify(r.detail) : '—'}</td>
                  <td className="td text-xs">{r.adresse_ip ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
