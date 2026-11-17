// Contenu d'un dossier : recherche, filtres, tri, pagination, sélection multiple, corbeille. Les filtres vivent dans l'URL
// (lien partageable, bouton retour du navigateur). Les boutons suivent le rôle dans le dossier ; le backend reste l'autorité.
import { ArrowLeft, Download, Eye, FilePlus2, FileUp, Pencil, RotateCcw, Search, Tags, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { errorMessage } from '../../shared/api/client'
import { useDebounce } from '../../shared/hooks/useDebounce'
import { formatDate, formatSize, plural } from '../../shared/lib/format'
import Badge from '../../shared/ui/Badge'
import ConfirmDialog from '../../shared/ui/ConfirmDialog'
import { EmptyState, ErrorBox, Loading } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import Pagination from '../../shared/ui/Pagination'
import { useToast } from '../../shared/hooks/useToast'
import { downloadVersion } from '../documents/api'
import AddDocumentModal from '../documents/components/AddDocumentModal'
import { ClassementBadges } from '../documents/components/ClassementBadges'
import ClassifyModal from '../documents/components/ClassifyModal'
import EditDocumentModal from '../documents/components/EditDocumentModal'
import NewVersionModal from '../documents/components/NewVersionModal'
import { StatusBadge } from '../documents/components/StatusBadge'
import { useDocumentMutations, useDocuments, useReferentiel } from '../documents/queries'
import type { DocumentFilters, DocumentMeta } from '../documents/types'
import { queryError, useDossier } from './queries'

const TAILLE = 15
type Dialog = { kind: 'add' } | { kind: 'edit' | 'version' | 'classify' | 'trash' | 'purge'; doc: DocumentMeta } | { kind: 'classify-many' } | null

import ErreurAcces from '../demandes/ErreurAcces'
import SousDossiers from './SousDossiers'

export function Component() {
  const dossierId = Number(useParams().dossierId)
  const dossier = useDossier(dossierId)
  const [params, setParams] = useSearchParams()
  const toast = useToast()
  const mutations = useDocumentMutations()
  const ref = useReferentiel()

  const corbeille = params.get('vue') === 'corbeille'
  const page = Number(params.get('page') ?? 1) || 1
  const [q, setQ] = useState(params.get('q') ?? '')
  const debouncedQ = useDebounce(q)
  const [dialog, setDialog] = useState<Dialog>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const filters: DocumentFilters = {
    dossier_id: dossierId,
    q: debouncedQ || undefined,
    statut: params.get('statut') || undefined,
    categorie_id: params.get('categorie') ? Number(params.get('categorie')) : undefined,
    type_id: params.get('type') ? Number(params.get('type')) : undefined,
    confidentialite: params.get('conf') || undefined,
    tri: (params.get('tri') as DocumentFilters['tri']) || 'date_desc',
    page,
    taille: TAILLE,
    corbeille,
  }
  const docs = useDocuments(filters)

  function setParam(key: string, value: string | null) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value); else next.delete(key)
      if (key !== 'page') next.delete('page')
      return next
    }, { replace: true })
    setSelected(new Set())
  }

  if (dossier.isPending) return <Loading />
  if (dossier.error || !dossier.data) return (dossier.error ? <ErreurAcces error={dossier.error} /> : <ErrorBox message="Dossier introuvable." />)

  const d = dossier.data
  const writable = !d.archive
  const mayAdd = d.peut_creer && writable
  const mayDelete = d.peut_modifier && writable
  const items = docs.data?.items ?? []
  const allSelected = items.length > 0 && items.every((i) => selected.has(i.id))
  const chosen = items.filter((i) => selected.has(i.id))
  const toggle = (id: number) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })

  async function download(doc: DocumentMeta) {
    try { await downloadVersion(doc.id, doc.version.numero, doc.version.nom_fichier) } catch (e) { toast.error(errorMessage(e)) }
  }

  const activeFilters = ['statut', 'categorie', 'type', 'conf'].some((k) => params.get(k))

  return (
    <>
      <PageHeader
        back={<Link to="/dossiers" className="mb-2 inline-flex items-center gap-1 text-sm text-cream-300 hover:text-gold-300"><ArrowLeft className="h-4 w-4" /> Tous les dossiers</Link>}
        title={d.nom}
        description={<>{d.division_nom}{(d.chemin ?? []).length > 1 ? ` · ${(d.chemin ?? []).map((c) => c.nom).join(' / ')}` : ''}{d.description ? ` · ${d.description}` : ''}</>}
        actions={mayAdd && !corbeille ? <button className="btn" onClick={() => setDialog({ kind: 'add' })}><FilePlus2 className="h-4 w-4" /> Ajouter un fichier</button> : null}
      />
      <SousDossiers d={d} />
      {d.nb_fichiers_masques > 0 && <p className="mb-3 text-sm text-cream-300">{d.nb_fichiers_masques} fichier(s) de ce dossier ne sont pas accessibles avec vos rôles ; vous pouvez demander l’accès depuis la page Demandes.</p>}
      {d.archive && <p className="card mb-4 border-amber-300/40 p-3 text-sm text-amber-100">Dossier archivé : lecture seule, et exclu de l’assistant.</p>}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-52 flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-cream-300" aria-hidden />
          <input className="input pl-9" type="search" placeholder="Rechercher par titre ou nom de fichier…" aria-label="Rechercher un fichier" value={q}
            onChange={(e) => { setQ(e.target.value); setParam('q', e.target.value || null) }} />
        </div>
        <select className="input w-auto" aria-label="Statut" value={params.get('statut') ?? ''} onChange={(e) => setParam('statut', e.target.value || null)}>
          <option value="">Tous les statuts</option><option value="ready">Prêt</option><option value="processing">Indexation</option><option value="pending">En attente</option><option value="error">Erreur</option>
        </select>
        <select className="input w-auto" aria-label="Catégorie" value={params.get('categorie') ?? ''} onChange={(e) => setParam('categorie', e.target.value || null)}>
          <option value="">Toutes catégories</option>{ref.data?.categories.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
        <select className="input w-auto" aria-label="Type" value={params.get('type') ?? ''} onChange={(e) => setParam('type', e.target.value || null)}>
          <option value="">Tous types</option>{ref.data?.types.map((t) => <option key={t.id} value={t.id}>{t.nom}</option>)}
        </select>
        <select className="input w-auto" aria-label="Confidentialité" value={params.get('conf') ?? ''} onChange={(e) => setParam('conf', e.target.value || null)}>
          <option value="">Toute confidentialité</option><option value="PUBLIC">Public</option><option value="INTERNE">Interne</option><option value="CONFIDENTIEL">Confidentiel</option>
        </select>
        <select className="input w-auto" aria-label="Tri" value={params.get('tri') ?? 'date_desc'} onChange={(e) => setParam('tri', e.target.value === 'date_desc' ? null : e.target.value)}>
          <option value="date_desc">Plus récents</option><option value="titre_asc">Titre A → Z</option><option value="titre_desc">Titre Z → A</option>
        </select>
        {activeFilters && <button className="btn-ghost" onClick={() => setParams((p) => { const n = new URLSearchParams(); if (p.get('vue')) n.set('vue', p.get('vue')!); return n }, { replace: true })}>Effacer les filtres</button>}
      </div>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1 rounded-lg border border-gold-500/30 p-0.5" role="tablist">
          <button role="tab" aria-selected={!corbeille} className={`rounded-md px-3 py-1 text-sm ${!corbeille ? 'bg-gold-500 font-semibold text-leaf-950' : 'text-cream-100 hover:bg-gold-500/15'}`} onClick={() => setParam('vue', null)}>Fichiers</button>
          <button role="tab" aria-selected={corbeille} className={`rounded-md px-3 py-1 text-sm ${corbeille ? 'bg-gold-500 font-semibold text-leaf-950' : 'text-cream-100 hover:bg-gold-500/15'}`} onClick={() => setParam('vue', 'corbeille')}>Corbeille</button>
        </div>
        {chosen.length > 0 && mayAdd && !corbeille && (
          <div className="flex items-center gap-2 text-sm text-cream-300">
            {plural(chosen.length, 'fichier sélectionné', 'fichiers sélectionnés')}
            <button className="btn-ghost" onClick={() => setDialog({ kind: 'classify-many' })}><Tags className="h-4 w-4" /> Classer</button>
          </div>
        )}
      </div>

      <ErrorBox message={queryError(docs)} />
      {docs.isPending ? <Loading /> : items.length === 0 ? (
        <EmptyState icon={<FileUp className="h-8 w-8" />} title={corbeille ? 'La corbeille est vide' : activeFilters || debouncedQ ? 'Aucun fichier ne correspond' : 'Aucun fichier dans ce dossier'}
          action={mayAdd && !corbeille && !activeFilters && !debouncedQ ? <button className="btn" onClick={() => setDialog({ kind: 'add' })}>Ajouter le premier fichier</button> : undefined}>
          {corbeille ? 'Les fichiers supprimés apparaissent ici et peuvent être restaurés.' : undefined}
        </EmptyState>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {mayAdd && !corbeille && <th className="th w-8"><input type="checkbox" aria-label="Tout sélectionner" className="accent-gold-500" checked={allSelected} onChange={() => setSelected(allSelected ? new Set() : new Set(items.map((i) => i.id)))} /></th>}
                <th className="th">Fichier</th><th className="th">Classement</th><th className="th">Statut</th><th className="th">Modifié</th><th className="th text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((doc) => (
                <tr key={doc.id} className={selected.has(doc.id) ? 'bg-gold-500/10' : 'hover:bg-leaf-700/40'}>
                  {mayAdd && !corbeille && <td className="td"><input type="checkbox" aria-label={`Sélectionner ${doc.titre}`} className="accent-gold-500" checked={selected.has(doc.id)} onChange={() => toggle(doc.id)} /></td>}
                  <td className="td min-w-56">
                    <Link to={`/dossiers/${d.id}/fichiers/${doc.id}`} className="font-medium text-cream-50 hover:text-gold-300">{doc.titre}</Link>
                    <p className="text-xs text-cream-300">{doc.version.nom_fichier} · {formatSize(doc.version.taille_octets)}{doc.version.nb_pages ? ` · ${doc.version.nb_pages} p.` : ''}{doc.version.ocr_utilise ? ' · OCR' : ''}</p>
                    <p className="text-xs text-cream-300">v{doc.version.numero} · {plural(doc.nb_versions, 'version')}</p>
                  </td>
                  <td className="td"><ClassementBadges doc={doc} /></td>
                  <td className="td">
                    <StatusBadge statut={doc.version.statut} />
                    {doc.version.statut === 'error' && doc.version.message_erreur && <p className="mt-1 max-w-48 text-xs text-red-200">{doc.version.message_erreur}</p>}
                  </td>
                  <td className="td whitespace-nowrap text-xs text-cream-300">{formatDate(doc.modifie_le)}<br />{doc.cree_par_nom ?? ''}</td>
                  <td className="td">
                    <div className="flex justify-end gap-0.5">
                      {corbeille ? (
                        mayDelete && (
                          <>
                            <button className="btn-icon" title="Restaurer" aria-label={`Restaurer ${doc.titre}`} onClick={() => void mutations.restore.mutateAsync(doc.id).then(() => toast.success('Fichier restauré.')).catch((e) => toast.error(errorMessage(e)))}><RotateCcw className="h-4 w-4" /></button>
                            <button className="btn-icon text-red-300" title="Supprimer définitivement" aria-label={`Supprimer définitivement ${doc.titre}`} onClick={() => setDialog({ kind: 'purge', doc })}><Trash2 className="h-4 w-4" /></button>
                          </>
                        )
                      ) : (
                        <>
                          <Link className="btn-icon" title="Ouvrir" aria-label={`Ouvrir ${doc.titre}`} to={`/dossiers/${d.id}/fichiers/${doc.id}`}><Eye className="h-4 w-4" /></Link>
                          <button className="btn-icon" title="Télécharger" aria-label={`Télécharger ${doc.titre}`} onClick={() => void download(doc)}><Download className="h-4 w-4" /></button>
                          {mayAdd && (
                            <>
                              <button className="btn-icon" title="Nouvelle version" aria-label={`Nouvelle version de ${doc.titre}`} onClick={() => setDialog({ kind: 'version', doc })}><FileUp className="h-4 w-4" /></button>
                              <button className="btn-icon" title="Classer" aria-label={`Classer ${doc.titre}`} onClick={() => setDialog({ kind: 'classify', doc })}><Tags className="h-4 w-4" /></button>
                              <button className="btn-icon" title="Modifier" aria-label={`Modifier ${doc.titre}`} onClick={() => setDialog({ kind: 'edit', doc })}><Pencil className="h-4 w-4" /></button>
                            </>
                          )}
                          {mayDelete && <button className="btn-icon text-red-300" title="Mettre à la corbeille" aria-label={`Supprimer ${doc.titre}`} onClick={() => setDialog({ kind: 'trash', doc })}><Trash2 className="h-4 w-4" /></button>}
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {docs.data && <Pagination page={docs.data.page} taille={docs.data.taille} total={docs.data.total} onPage={(p) => setParam('page', p === 1 ? null : String(p))} />}
      {corbeille && <p className="mt-3 text-xs text-cream-300"><Badge tone="gray">Info</Badge> Les fichiers de la corbeille ne sont plus visibles dans le dossier ni interrogés par l’assistant.</p>}

      {dialog?.kind === 'add' && <AddDocumentModal dossier={d} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'edit' && <EditDocumentModal doc={dialog.doc} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'version' && <NewVersionModal doc={dialog.doc} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'classify' && <ClassifyModal docs={[dialog.doc]} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'classify-many' && <ClassifyModal docs={chosen} onClose={() => setDialog(null)} onDone={() => setSelected(new Set())} />}
      {dialog?.kind === 'trash' && (
        <ConfirmDialog title="Mettre à la corbeille" confirmLabel="Mettre à la corbeille" onClose={() => setDialog(null)}
          onConfirm={async () => { await mutations.remove.mutateAsync(dialog.doc.id); toast.success('Fichier placé dans la corbeille.') }}>
          Mettre <span className="font-semibold text-gold-300">« {dialog.doc.titre} »</span> dans la corbeille ? Il ne sera plus visible dans le dossier ni interrogé par l’assistant, mais pourra être restauré.
        </ConfirmDialog>
      )}
      {dialog?.kind === 'purge' && (
        <ConfirmDialog title="Supprimer définitivement" confirmLabel="Supprimer définitivement" onClose={() => setDialog(null)}
          onConfirm={async () => { await mutations.purge.mutateAsync(dialog.doc.id); toast.success('Fichier supprimé définitivement.') }}>
          Supprimer définitivement <span className="font-semibold text-gold-300">« {dialog.doc.titre} »</span>, toutes ses versions et leurs passages indexés ? Cette action est irréversible.
        </ConfirmDialog>
      )}
    </>
  )
}
