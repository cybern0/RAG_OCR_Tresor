// Tableau de bord des documents : liste des métadonnées (jamais le contenu), statut d'indexation,
// ajout, modification, suppression. L'UTILISATEUR ne voit que son service ; l'ADMIN tous (avec filtre).
import { useCallback, useEffect, useState } from 'react'
import { listDocuments } from '../../api/documents'
import { listServices } from '../../api/structure'
import { ErrorBox, Loading } from '../../components/ui/Feedback'
import { useAuth } from '../../hooks/useAuth'
import { useLoad } from '../../hooks/useLoad'
import type { DocumentMeta, Statut } from '../../types/document'
import AddDocumentForm from './AddDocumentForm'
import DeleteDocumentDialog from './DeleteDocumentDialog'
import UpdateDocumentForm from './UpdateDocumentForm'

const STATUS: Record<Statut, { label: string; cls: string }> = {
  pending: { label: 'En attente', cls: 'border-cream-300/60 text-cream-100' },
  processing: { label: 'Indexation…', cls: 'border-gold-400 bg-gold-500/15 text-gold-300' },
  ready: { label: 'Prêt', cls: 'border-emerald-300/70 bg-emerald-400/15 text-emerald-100' },
  error: { label: 'Erreur', cls: 'border-red-300/70 bg-red-400/15 text-red-100' },
}

const formatSize = (bytes: number | null) =>
  bytes === null ? '—' : bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} Ko` : `${(bytes / 1024 / 1024).toFixed(1)} Mo`

const formatDate = (iso: string) => new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })

export default function DashboardDocuments() {
  const { user, can } = useAuth()
  const isAdmin = user?.role === 'ADMIN'
  const [serviceFilter, setServiceFilter] = useState<number | null>(null)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<DocumentMeta | null>(null)
  const [deleting, setDeleting] = useState<DocumentMeta | null>(null)

  const fetchDocs = useCallback(() => listDocuments(serviceFilter), [serviceFilter])
  const docs = useLoad(fetchDocs)
  const services = useLoad(useCallback(() => (isAdmin ? listServices() : Promise.resolve([])), [isAdmin]))

  // Tant qu'un document est en cours d'indexation, on actualise la liste
  const hasPending = (docs.data ?? []).some((d) => d.statut === 'pending' || d.statut === 'processing')
  const reload = docs.reload
  useEffect(() => {
    if (!hasPending) return
    const timer = setInterval(() => void reload(), 3000)
    return () => clearInterval(timer)
  }, [hasPending, reload])

  const done = () => {
    setAdding(false)
    setEditing(null)
    setDeleting(null)
    void reload()
  }

  const list = docs.data ?? []
  const serviceList = services.data ?? []

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gold-400">Documents</h1>
          <p className="text-sm text-cream-300">
            {isAdmin ? 'Tous les services' : `Service : ${user?.service_nom ?? 'aucun'}`} · le contenu n'est consultable que via le chatbot
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isAdmin && (
            <select aria-label="Filtrer par service" className="input w-auto" value={serviceFilter ?? ''} onChange={(e) => setServiceFilter(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Tous les services</option>
              {serviceList.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          )}
          {can('document.creer') && <button className="btn" onClick={() => setAdding(true)}>+ Ajouter un document</button>}
        </div>
      </div>

      <ErrorBox message={docs.error} />
      {docs.loading ? (
        <Loading />
      ) : list.length === 0 ? (
        <div className="card p-10 text-center text-cream-300">Aucun document pour le moment.</div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className="th">Titre</th>
                {isAdmin && <th className="th">Service</th>}
                <th className="th">Statut</th>
                <th className="th">Détails</th>
                <th className="th">Ajouté</th>
                <th className="th text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {list.map((d) => (
                <tr key={d.id}>
                  <td className="td">
                    <p className="font-medium">{d.titre}</p>
                    <p className="text-xs text-cream-300">{d.nom_fichier}</p>
                  </td>
                  {isAdmin && <td className="td">{d.service_nom}</td>}
                  <td className="td">
                    <span className={`badge ${STATUS[d.statut].cls}`}>{STATUS[d.statut].label}</span>
                    {d.statut === 'error' && d.message_erreur && <p className="mt-1 max-w-xs text-xs text-red-200">{d.message_erreur}</p>}
                  </td>
                  <td className="td text-xs text-cream-300">
                    {formatSize(d.taille_octets)}
                    {d.nb_pages ? ` · ${d.nb_pages} p.` : ''}
                    {d.ocr_utilise ? ' · OCR' : ''}
                    {d.has_tabular ? ' · tableaux' : ''}
                  </td>
                  <td className="td text-xs text-cream-300">{formatDate(d.cree_le)}<br />{d.cree_par_nom ?? ''}</td>
                  <td className="td">
                    <div className="flex justify-end gap-2">
                      {can('document.modifier') && <button className="btn-ghost" onClick={() => setEditing(d)}>Modifier</button>}
                      {can('document.supprimer') && <button className="btn-danger" onClick={() => setDeleting(d)}>Supprimer</button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {adding && (
        <AddDocumentForm isAdmin={isAdmin} ownServiceName={user?.service_nom ?? null} services={serviceList} defaultServiceId={user?.service_id ?? null} onClose={() => setAdding(false)} onDone={done} />
      )}
      {editing && <UpdateDocumentForm doc={editing} isAdmin={isAdmin} services={serviceList} onClose={() => setEditing(null)} onDone={done} />}
      {deleting && <DeleteDocumentDialog doc={deleting} onClose={() => setDeleting(null)} onDone={done} />}
    </section>
  )
}
