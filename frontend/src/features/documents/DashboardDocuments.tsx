// Dossiers et fichiers : à gauche les dossiers auxquels on a accès (avec son rôle), à droite les fichiers du dossier
// choisi, avec statut d'indexation, historique des versions, aperçu et téléchargement.
// Les boutons suivent le rôle dans le dossier ; le vrai contrôle est fait par le backend.
import { useCallback, useEffect, useState } from 'react'
import { listDocuments } from '../../api/documents'
import { listDossiers } from '../../api/dossiers'
import { ErrorBox, Loading } from '../../components/ui/Feedback'
import { useLoad } from '../../hooks/useLoad'
import { formatDate, formatSize } from '../../lib/fichiers'
import { canAdd, canDelete, roleLabel } from '../../types/dossier'
import type { DocumentMeta } from '../../types/document'
import AddDocumentForm from './AddDocumentForm'
import DeleteDocumentDialog from './DeleteDocumentDialog'
import NewVersionForm from './NewVersionForm'
import { StatusBadge } from './StatusBadge'
import UpdateDocumentForm from './UpdateDocumentForm'
import VersionsDialog from './VersionsDialog'

export default function DashboardDocuments() {
  const dossiers = useLoad(listDossiers)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<DocumentMeta | null>(null)
  const [versioning, setVersioning] = useState<DocumentMeta | null>(null)
  const [history, setHistory] = useState<DocumentMeta | null>(null)
  const [deleting, setDeleting] = useState<DocumentMeta | null>(null)

  const folders = dossiers.data ?? []
  const current = folders.find((d) => d.id === selectedId) ?? folders[0] ?? null
  const currentId = current?.id ?? null

  const docs = useLoad(useCallback(() => (currentId ? listDocuments(currentId) : Promise.resolve([])), [currentId]))
  const list = docs.data ?? []

  // Tant qu'une version est en cours d'indexation, on actualise la liste
  const hasPending = list.some((d) => d.version.statut === 'pending' || d.version.statut === 'processing')
  const reloadDocs = docs.reload
  useEffect(() => {
    if (!hasPending) return
    const timer = setInterval(() => void reloadDocs(), 3000)
    return () => clearInterval(timer)
  }, [hasPending, reloadDocs])

  const done = () => {
    setAdding(false)
    setEditing(null)
    setVersioning(null)
    setDeleting(null)
    void reloadDocs()
    void dossiers.reload()
  }

  const role = current?.mon_role
  const writable = !!current && !current.archive

  return (
    <div className="grid gap-4 md:grid-cols-[16rem_1fr]">
      <aside className="card max-h-[75svh] overflow-y-auto p-3">
        <h2 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-gold-400">Mes dossiers</h2>
        {dossiers.loading ? <Loading /> : (
          <ul className="space-y-1">
            {folders.map((d) => (
              <li key={d.id}>
                <button onClick={() => setSelectedId(d.id)} aria-current={current?.id === d.id ? 'true' : undefined}
                  className={`w-full rounded-lg px-2 py-2 text-left text-sm hover:bg-gold-500/15 ${current?.id === d.id ? 'bg-gold-500/20 text-gold-300' : 'text-cream-100'}`}>
                  <span className="block truncate font-medium">{d.nom}</span>
                  <span className="block text-xs text-cream-300">
                    {d.nb_fichiers} fichier{d.nb_fichiers > 1 ? 's' : ''} · {roleLabel(d.mon_role)}{d.archive ? ' · archivé' : ''}
                  </span>
                </button>
              </li>
            ))}
            {folders.length === 0 && <li className="px-2 text-sm text-cream-300">Aucun dossier : un administrateur doit vous donner accès à un dossier.</li>}
          </ul>
        )}
      </aside>

      <section className="space-y-4">
        <ErrorBox message={dossiers.error ?? docs.error} />
        {current && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h1 className="text-xl font-bold text-gold-400">{current.nom}</h1>
                <p className="text-sm text-cream-300">
                  Votre rôle : {roleLabel(current.mon_role)}
                  {current.description ? ` · ${current.description}` : ''}
                </p>
              </div>
              {role && canAdd(role) && writable && <button className="btn" onClick={() => setAdding(true)}>+ Ajouter un fichier</button>}
            </div>
            {current.archive && <p className="card p-3 text-sm text-gold-300">Dossier archivé : lecture seule, et exclu du chatbot.</p>}

            {docs.loading ? <Loading /> : list.length === 0 ? (
              <div className="card p-10 text-center text-cream-300">Aucun fichier dans ce dossier.</div>
            ) : (
              <div className="card overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className="th">Fichier</th>
                      <th className="th">Version</th>
                      <th className="th">Statut</th>
                      <th className="th">Détails</th>
                      <th className="th">Dernière modification</th>
                      <th className="th text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((d) => (
                      <tr key={d.id}>
                        <td className="td"><p className="font-medium">{d.titre}</p><p className="text-xs text-cream-300">{d.version.nom_fichier}</p></td>
                        <td className="td text-xs text-cream-300">v{d.version.numero}<br />{d.nb_versions} version{d.nb_versions > 1 ? 's' : ''}</td>
                        <td className="td">
                          <StatusBadge statut={d.version.statut} />
                          {d.version.statut === 'error' && d.version.message_erreur && <p className="mt-1 max-w-xs text-xs text-red-200">{d.version.message_erreur}</p>}
                        </td>
                        <td className="td text-xs text-cream-300">
                          {formatSize(d.version.taille_octets)}
                          {d.version.nb_pages ? ` · ${d.version.nb_pages} p.` : ''}
                          {d.version.ocr_utilise ? ' · OCR' : ''}
                          {d.has_tabular ? ' · tableaux' : ''}
                          {d.has_image ? ' · images' : ''}
                        </td>
                        <td className="td text-xs text-cream-300">{formatDate(d.version.cree_le)}<br />{d.version.cree_par_nom ?? ''}</td>
                        <td className="td">
                          <div className="flex flex-wrap justify-end gap-2">
                            <button className="btn-ghost" onClick={() => setHistory(d)}>Versions / aperçu</button>
                            {role && canAdd(role) && writable && (
                              <>
                                <button className="btn-ghost" onClick={() => setVersioning(d)}>Nouvelle version</button>
                                <button className="btn-ghost" onClick={() => setEditing(d)}>Modifier</button>
                              </>
                            )}
                            {role && canDelete(role) && writable && <button className="btn-danger" onClick={() => setDeleting(d)}>Supprimer</button>}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      {adding && current && <AddDocumentForm dossier={current} onClose={() => setAdding(false)} onDone={done} />}
      {editing && <UpdateDocumentForm doc={editing} onClose={() => setEditing(null)} onDone={done} />}
      {versioning && <NewVersionForm doc={versioning} onClose={() => setVersioning(null)} onDone={done} />}
      {history && role && (
        <VersionsDialog doc={history} canDelete={canDelete(role) && writable} onClose={() => setHistory(null)} onChanged={() => { void reloadDocs() }} />
      )}
      {deleting && <DeleteDocumentDialog doc={deleting} onClose={() => setDeleting(null)} onDone={done} />}
    </div>
  )
}
