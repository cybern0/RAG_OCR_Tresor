// Liste à plat de tous les fichiers accessibles (plus de dossiers ni d'arborescence) : recherche, filtre par rôle
// (un fichier peut avoir plusieurs rôles, un agent en porter plusieurs), filtre par division (chef de service),
// statut, tri, pagination, sélection multiple, corbeille. Les filtres vivent dans l'URL ; le backend reste l'autorité.
// Les filtres catégorie / type / confidentialité ont été retirés : ces données restent des métadonnées de classement
// (badges, statistiques, règles automatiques), la visibilité étant déjà gouvernée par division et rôles côté serveur.
import { Download, Eye, FilePlus2, FileUp, Pencil, RotateCcw, Search, Tags, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
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
import { useDocumentMutations, useDocuments, useFiltres } from '../documents/queries'
import type { DocumentFilters, DocumentMeta } from '../documents/types'

const TAILLE = 15
type Dialog = { kind: 'add' } | { kind: 'edit' | 'version' | 'classify' | 'trash' | 'purge'; doc: DocumentMeta } | { kind: 'classify-many' } | null

export function Component() {
  const [params, setParams] = useSearchParams()
  const toast = useToast()
  const mutations = useDocumentMutations()
  const filtres = useFiltres()

  const corbeille = params.get('vue') === 'corbeille'
  const page = Number(params.get('page') ?? 1) || 1
  const [q, setQ] = useState(params.get('q') ?? '')
  const debouncedQ = useDebounce(q)
  const [dialog, setDialog] = useState<Dialog>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const divisionsDepot = filtres.data?.divisions.filter((d) => filtres.data?.depot_divisions.includes(d.id)) ?? []

  const filters: DocumentFilters = {
    q: debouncedQ || undefined,
    statut: params.get('statut') || undefined,
    role_id: params.get('role') ? Number(params.get('role')) : undefined,
    division_id: params.get('division') ? Number(params.get('division')) : undefined,
    tri: (params.get('tri') as DocumentFilters['tri']) || 'date_desc',
    page,
    taille: TAILLE,
    corbeille,
    a_classer: params.get('a_classer') === '1',
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

  const mayAdd = divisionsDepot.length > 0
  const items = docs.data?.items ?? []
  const allSelected = items.length > 0 && items.every((i) => selected.has(i.id))
  const chosen = items.filter((i) => selected.has(i.id))
  const toggle = (id: number) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })

  async function download(doc: DocumentMeta) {
    try { await downloadVersion(doc.id, doc.version.numero, doc.version.nom_fichier) } catch (e) { toast.error(errorMessage(e)) }
  }

  const activeFilters = ['statut', 'role', 'division', 'a_classer'].some((k) => params.get(k))
  const roleLibelle = filtres.data?.roles.find((r) => r.id === filters.role_id)

  return (
    <>
      <PageHeader title="Fichiers" description="Tous les fichiers auxquels vos rôles donnent accès, sans arborescence : déposez directement et filtrez par classe, par rôle ou par division."
        actions={mayAdd && !corbeille ? <button className="btn" onClick={() => setDialog({ kind: 'add' })}><FilePlus2 className="h-4 w-4" /> Ajouter un fichier</button> : null} />
      {filtres.data && filtres.data.divisions.length > 1 && (
        <p className="mb-3 text-sm text-cream-300">{filtres.data.divisions.length} divisions dans votre périmètre — utilisez le filtre « Division » pour vous concentrer sur l'une d'elles.</p>
      )}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-52 flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-cream-300" aria-hidden />
          <input className="input pl-9" type="search" placeholder="Rechercher par titre ou nom de fichier…" aria-label="Rechercher un fichier" value={q}
            onChange={(e) => { setQ(e.target.value); setParam('q', e.target.value || null) }} />
        </div>
        <select className="input w-auto" aria-label="Rôle (classe)" value={params.get('role') ?? ''} onChange={(e) => setParam('role', e.target.value || null)}>
          <option value="">Tous les rôles</option>
          {(filtres.data?.roles ?? []).map((r) => <option key={r.id} value={r.id}>{r.libelle}{r.division_nom ? ` · ${r.division_nom}` : ''}</option>)}
        </select>
        {(filtres.data?.divisions.length ?? 0) > 1 && (
          <select className="input w-auto" aria-label="Division" value={params.get('division') ?? ''} onChange={(e) => setParam('division', e.target.value || null)}>
            <option value="">Toutes mes divisions</option>
            {(filtres.data?.divisions ?? []).map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
          </select>
        )}
        <select className="input w-auto" aria-label="Statut" value={params.get('statut') ?? ''} onChange={(e) => setParam('statut', e.target.value || null)}>
          <option value="">Tous les statuts</option><option value="ready">Prêt</option><option value="processing">Indexation</option><option value="pending">En attente</option><option value="error">Erreur</option>
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
          <button role="tab" aria-selected={filters.a_classer} className={`rounded-md px-3 py-1 text-sm ${filters.a_classer ? 'bg-gold-500 font-semibold text-leaf-950' : 'text-cream-100 hover:bg-gold-500/15'}`} onClick={() => setParam('a_classer', filters.a_classer ? null : '1')}>À classer</button>
        </div>
        {chosen.length > 0 && !corbeille && (
          <div className="flex items-center gap-2 text-sm text-cream-300">
            {plural(chosen.length, 'fichier sélectionné', 'fichiers sélectionnés')}
            <button className="btn-ghost" onClick={() => setDialog({ kind: 'classify-many' })}><Tags className="h-4 w-4" /> Classer</button>
          </div>
        )}
      </div>
      {roleLibelle && <p className="mb-3 text-sm text-cream-300">Filtré par rôle : <Badge tone="gold">{roleLibelle.libelle}{roleLibelle.division_nom ? ` · ${roleLibelle.division_nom}` : ''}</Badge> — seuls les fichiers portant ce rôle (et accessibles avec vos droits) apparaissent.</p>}

      <ErrorBox message={docs.error ? errorMessage(docs.error) : null} />
      {docs.isPending ? <Loading /> : items.length === 0 ? (
        <EmptyState icon={<FileUp className="h-8 w-8" />} title={corbeille ? 'La corbeille est vide' : activeFilters || debouncedQ ? 'Aucun fichier ne correspond' : 'Aucun fichier accessible'}
          action={mayAdd && !corbeille && !activeFilters && !debouncedQ ? <button className="btn" onClick={() => setDialog({ kind: 'add' })}>Ajouter le premier fichier</button> : undefined}>
          {corbeille ? 'Les fichiers supprimés apparaissent ici et peuvent être restaurés.' : undefined}
        </EmptyState>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {!corbeille && <th className="th w-8"><input type="checkbox" aria-label="Tout sélectionner" className="accent-gold-500" checked={allSelected} onChange={() => setSelected(allSelected ? new Set() : new Set(items.map((i) => i.id)))} /></th>}
                <th className="th">Fichier</th><th className="th">Division</th><th className="th">Classement</th><th className="th">Statut</th><th className="th">Modifié</th><th className="th text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((doc) => (
                <tr key={doc.id} className={selected.has(doc.id) ? 'bg-gold-500/10' : 'hover:bg-leaf-700/40'}>
                  {!corbeille && <td className="td"><input type="checkbox" aria-label={`Sélectionner ${doc.titre}`} className="accent-gold-500" checked={selected.has(doc.id)} onChange={() => toggle(doc.id)} /></td>}
                  <td className="td min-w-56">
                    <Link to={`/fichiers/${doc.id}`} className="font-medium text-cream-50 hover:text-gold-300">{doc.titre}</Link>
                    <p className="text-xs text-cream-300">{doc.version.nom_fichier} · {formatSize(doc.version.taille_octets)}{doc.version.nb_pages ? ` · ${doc.version.nb_pages} p.` : ''}{doc.version.ocr_utilise ? ' · OCR' : ''}</p>
                    <p className="text-xs text-cream-300">v{doc.version.numero} · {plural(doc.nb_versions, 'version')}</p>
                  </td>
                  <td className="td text-sm text-cream-200">{doc.division_nom}</td>
                  <td className="td"><ClassementBadges doc={doc} /></td>
                  <td className="td">
                    <StatusBadge statut={doc.version.statut} />
                    {doc.version.statut === 'error' && doc.version.message_erreur && <p className="mt-1 max-w-48 text-xs text-red-200">{doc.version.message_erreur}</p>}
                  </td>
                  <td className="td whitespace-nowrap text-xs text-cream-300">{formatDate(doc.modifie_le)}<br />{doc.cree_par_nom ?? ''}</td>
                  <td className="td">
                    <div className="flex justify-end gap-0.5">
                      {corbeille ? (
                        <>
                          {doc.droits.includes('supprimer') && <button className="btn-icon" title="Restaurer" aria-label={`Restaurer ${doc.titre}`} onClick={() => void mutations.restore.mutateAsync(doc.id).then(() => toast.success('Fichier restauré.')).catch((e) => toast.error(errorMessage(e)))}><RotateCcw className="h-4 w-4" /></button>}
                          {doc.droits.includes('purger') && <button className="btn-icon text-red-300" title="Supprimer définitivement" aria-label={`Supprimer définitivement ${doc.titre}`} onClick={() => setDialog({ kind: 'purge', doc })}><Trash2 className="h-4 w-4" /></button>}
                        </>
                      ) : (
                        <>
                          <Link className="btn-icon" title="Ouvrir" aria-label={`Ouvrir ${doc.titre}`} to={`/fichiers/${doc.id}`}><Eye className="h-4 w-4" /></Link>
                          <button className="btn-icon" title="Télécharger" aria-label={`Télécharger ${doc.titre}`} onClick={() => void download(doc)}><Download className="h-4 w-4" /></button>
                          {doc.droits.includes('ajouter_version') && (
                            <>
                              <button className="btn-icon" title="Nouvelle version" aria-label={`Nouvelle version de ${doc.titre}`} onClick={() => setDialog({ kind: 'version', doc })}><FileUp className="h-4 w-4" /></button>
                              <button className="btn-icon" title="Modifier" aria-label={`Modifier ${doc.titre}`} onClick={() => setDialog({ kind: 'edit', doc })}><Pencil className="h-4 w-4" /></button>
                            </>
                          )}
                          {doc.droits.includes('classer') && <button className="btn-icon" title="Classer" aria-label={`Classer ${doc.titre}`} onClick={() => setDialog({ kind: 'classify', doc })}><Tags className="h-4 w-4" /></button>}
                          {doc.droits.includes('supprimer') && <button className="btn-icon text-red-300" title="Mettre à la corbeille" aria-label={`Supprimer ${doc.titre}`} onClick={() => setDialog({ kind: 'trash', doc })}><Trash2 className="h-4 w-4" /></button>}
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
      {corbeille && <p className="mt-3 text-xs text-cream-300"><Badge tone="gray">Info</Badge> Les fichiers de la corbeille ne sont plus visibles dans la liste ni interrogés par l’assistant.</p>}

      {dialog?.kind === 'add' && <AddDocumentModal divisions={divisionsDepot} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'edit' && <EditDocumentModal doc={dialog.doc} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'version' && <NewVersionModal doc={dialog.doc} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'classify' && <ClassifyModal docs={[dialog.doc]} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'classify-many' && <ClassifyModal docs={chosen} onClose={() => setDialog(null)} onDone={() => setSelected(new Set())} />}
      {dialog?.kind === 'trash' && (
        <ConfirmDialog title="Mettre à la corbeille" confirmLabel="Mettre à la corbeille" onClose={() => setDialog(null)}
          onConfirm={async () => { await mutations.remove.mutateAsync(dialog.doc.id); toast.success('Fichier placé dans la corbeille.') }}>
          Mettre <span className="font-semibold text-gold-300">« {dialog.doc.titre} »</span> dans la corbeille ? Il ne sera plus visible ni interrogé par l’assistant, mais pourra être restauré.
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
