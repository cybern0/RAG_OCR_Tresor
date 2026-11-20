// Fiche d'un fichier : aperçu de la version choisie, informations, affectations aux agents, historique des versions, commentaires.
import { ArrowLeft, Download, FileUp, Pencil, Tags, Trash2, UserSquare } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { errorMessage } from '../../shared/api/client'
import { formatDate, formatSize, plural } from '../../shared/lib/format'
import ConfirmDialog from '../../shared/ui/ConfirmDialog'
import Badge from '../../shared/ui/Badge'
import ErreurAcces from '../demandes/ErreurAcces'
import { ErrorBox, Loading } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import { useToast } from '../../shared/hooks/useToast'
import { downloadVersion } from './api'
import { ClassementBadges } from './components/ClassementBadges'
import ClassifyModal from './components/ClassifyModal'
import AffectationModal from './components/AffectationModal'
import { CommentsPanel } from './components/CommentsPanel'
import EditDocumentModal from './components/EditDocumentModal'
import NewVersionModal from './components/NewVersionModal'
import ReindexModal from './components/ReindexModal'
import { PreviewStored } from './components/PreviewStored'
import { StatusBadge } from './components/StatusBadge'
import { VersionsPanel } from './components/VersionsPanel'
import { useDocument, useDocumentMutations, useVersions } from './queries'

type Dialog = 'edit' | 'version' | 'classify' | 'affect' | 'delete' | 'reindex' | null

export function Component() {
  const documentId = Number(useParams().documentId)
  const id = documentId
  const doc = useDocument(id)
  const versions = useVersions(id)
  const navigate = useNavigate()
  const toast = useToast()
  const { remove } = useDocumentMutations()
  const [dialog, setDialog] = useState<Dialog>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [reindexOf, setReindexOf] = useState<number | null>(null)

  if (doc.isPending) return <Loading />
  if (doc.error || !doc.data) return (doc.error ? <ErreurAcces error={doc.error} documentId={Number(documentId)} /> : <ErrorBox message="Fichier introuvable." />)

  const d = doc.data
  const list = versions.data ?? []
  const current = list.find((v) => v.numero === selected) ?? list.find((v) => v.est_courante) ?? list[0] ?? null
  const writable = !d.corbeille_le
  const mayAdd = d.droits.includes('ajouter_version') && writable
  const mayDelete = d.droits.includes('purger') && writable
  const mayReindex = d.droits.includes('modifier') && writable

  return (
    <>
      <PageHeader
        back={<Link to="/fichiers" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-navy-600"><ArrowLeft className="h-4 w-4" /> Tous les fichiers</Link>}
        title={d.titre}
        description={<span className="flex flex-wrap items-center gap-2"><Badge tone="gray">{d.division_nom}</Badge> <StatusBadge statut={d.version.statut} /> {plural(d.nb_versions, 'version')} · modifié le {formatDate(d.modifie_le)}</span>}
        actions={(
          <>
            {current && <button className="btn-ghost" onClick={() => void downloadVersion(d.id, current.numero, current.nom_fichier).catch((e) => toast.error(errorMessage(e)))}><Download className="h-4 w-4" /> Télécharger v{current.numero}</button>}
            {mayAdd && <button className="btn" onClick={() => setDialog('version')}><FileUp className="h-4 w-4" /> Nouvelle version</button>}
          </>
        )}
      />
      {d.corbeille_le && <p className="card mb-4 border-amber-300 p-3 text-sm text-amber-800">Ce fichier est dans la corbeille.</p>}

      <div className="grid gap-5 lg:grid-cols-[1fr_22rem]">
        <section className="card min-w-0 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">Aperçu{current ? ` · version ${current.numero}` : ''}</h2>
          {current ? <PreviewStored key={`${d.id}-${current.numero}-${current.statut === 'error' ? 'erreur' : 'ok'}`} documentId={d.id} numero={current.numero} mode={current.apercu} tall /> : <Loading />}
        </section>

        <aside className="space-y-5">
          <section className="card p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-navy-700">Informations</h2>
              <div className="flex gap-0.5">
                {mayAdd && <button className="btn-icon" title="Métadonnées" aria-label="Métadonnées" onClick={() => setDialog('classify')}><Tags className="h-4 w-4" /></button>}
                {mayAdd && <button className="btn-icon" title="Modifier" aria-label="Modifier" onClick={() => setDialog('edit')}><Pencil className="h-4 w-4" /></button>}
                {mayDelete && <button className="btn-icon text-red-600" title="Mettre à la corbeille" aria-label="Mettre à la corbeille" onClick={() => setDialog('delete')}><Trash2 className="h-4 w-4" /></button>}
              </div>
            </div>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-xs text-slate-600">Affectations</dt>
                <dd className="mt-1">
                  <div className="flex flex-wrap items-center gap-1">
                    {d.affectations.length === 0 ? <Badge tone="amber">À affecter</Badge>
                      : d.affectations.map((a) => <Badge key={a.id} tone="green">{a.prenom} {a.nom}</Badge>)}
                    {d.droits.includes('affecter') && (
                      <button className="btn-icon" title="Affecter à des agents" aria-label="Affecter à des agents" onClick={() => setDialog('affect')}><UserSquare className="h-4 w-4" /></button>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-slate-600">Les agents affectés (par le chef) lisent ce fichier ; sans affectation, l'accès se demande.</p>
                </dd>
              </div>
              <div><dt className="text-xs text-slate-600">Métadonnées</dt><dd className="mt-1"><ClassementBadges doc={d} max={8} /></dd></div>
              <div><dt className="text-xs text-slate-600">Fichier</dt><dd>{d.version.nom_fichier} · {formatSize(d.version.taille_octets)}</dd></div>
              <div><dt className="text-xs text-slate-600">Lecture</dt><dd>{[d.has_tabular && 'tableaux', d.has_image && 'images', d.version.ocr_utilise && 'OCR'].filter(Boolean).join(' · ') || 'Texte seul'}</dd></div>
              <div><dt className="text-xs text-slate-600">Créé par</dt><dd>{d.cree_par_nom ?? '—'} le {formatDate(d.cree_le)}</dd></div>
            </dl>
          </section>

          <section className="card p-4">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">Versions</h2>
            {versions.isPending ? <Loading className="py-4" /> : current && (
              <VersionsPanel documentId={d.id} versions={list} selected={current.numero} onSelect={setSelected} canDelete={mayDelete}
                onReindex={mayReindex ? (n) => { setReindexOf(n); setDialog('reindex') } : undefined} />
            )}
            <ErrorBox message={versions.error ? errorMessage(versions.error) : null} />
          </section>

          {d.droits.includes('ajouter_version') && (
            <section className="card p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">Commentaires</h2>
              <CommentsPanel documentId={d.id} />
            </section>
          )}
        </aside>
      </div>

      {dialog === 'edit' && <EditDocumentModal doc={d} onClose={() => setDialog(null)} />}
      {dialog === 'version' && <NewVersionModal doc={d} onClose={() => setDialog(null)} />}
      {dialog === 'reindex' && list.find((v) => v.numero === reindexOf) && (
        <ReindexModal doc={d} version={list.find((v) => v.numero === reindexOf)!} onClose={() => setDialog(null)} />
      )}
      {dialog === 'classify' && <ClassifyModal docs={[d]} onClose={() => setDialog(null)} />}
      {dialog === 'affect' && <AffectationModal doc={d} onClose={() => setDialog(null)} />}
      {dialog === 'delete' && (
        <ConfirmDialog title="Mettre à la corbeille" confirmLabel="Mettre à la corbeille" onClose={() => setDialog(null)}
          onConfirm={async () => { await remove.mutateAsync(d.id); toast.success('Fichier placé dans la corbeille.'); navigate('/fichiers', { replace: true }) }}>
          Mettre <span className="font-semibold text-navy-600">« {d.titre} »</span> dans la corbeille ?
        </ConfirmDialog>
      )}
    </>
  )
}
