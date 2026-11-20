// Liste à plat de tous les fichiers accessibles (plus de dossiers ni d'arborescence) : recherche, filtre
// « affecté à » (un fichier est affecté manuellement à un ou plusieurs agents par le chef), filtre par division
// (chef de service), statut, tri, pagination, sélection multiple, corbeille. Les filtres vivent dans l'URL ;
// le backend reste l'autorité. Les filtres catégorie / type / confidentialité ont été retirés : ces données
// restent des métadonnées (badges, statistiques, règles automatiques), l'accès étant gouverné par les affectations.
import { Download, Eye, FilePlus2, FileUp, Pencil, RotateCcw, Search, Tags, Trash2, UserSquare } from 'lucide-react'
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
import AffectationModal from '../documents/components/AffectationModal'
import NewVersionModal from '../documents/components/NewVersionModal'
import { StatusBadge } from '../documents/components/StatusBadge'
import { useDocumentMutations, useDocuments, useFiltres } from '../documents/queries'
import type { DocumentFilters, DocumentMeta } from '../documents/types'

const TAILLE = 15
type Dialog = { kind: 'add' } | { kind: 'edit' | 'version' | 'classify' | 'affect' | 'trash' | 'purge'; doc: DocumentMeta } | { kind: 'classify-many' } | null

/** Noms des agents affectés (max 2) ou l'état « à affecter » : l'accès se décide ici, plus par les classes. */
function AffectationBadges({ doc, max = 2 }: { doc: DocumentMeta; max?: number }) {
  if (doc.affectations.length === 0) return <Badge tone="amber">À affecter</Badge>
  return (
    <div className="flex flex-wrap items-center gap-1">
      {doc.affectations.slice(0, max).map((a) => (
        <Badge key={a.id} tone="green">{a.prenom} {a.nom}</Badge>
      ))}
      {doc.affectations.length > max && <span className="text-xs text-slate-600">+{doc.affectations.length - max}</span>}
    </div>
  )
}

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
    agent_id: params.get('agent') ? Number(params.get('agent')) : undefined,
    division_id: params.get('division') ? Number(params.get('division')) : undefined,
    tri: (params.get('tri') as DocumentFilters['tri']) || 'date_desc',
    page,
    taille: TAILLE,
    corbeille,
    a_affecter: params.get('a_affecter') === '1',
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

  const activeFilters = ['statut', 'agent', 'division', 'a_affecter'].some((k) => params.get(k))
  const agentChoisi = filtres.data?.agents.find((x) => x.id === filters.agent_id)

  return (
    <>
      <PageHeader title="Fichiers" description="Tous les fichiers auxquels vous avez accès, sans arborescence : déposez directement, le chef affecte chaque fichier aux agents de sa division, et filtrez par agent ou par division."
        actions={mayAdd && !corbeille ? <button className="btn" onClick={() => setDialog({ kind: 'add' })}><FilePlus2 className="h-4 w-4" /> Ajouter un fichier</button> : null} />
      {filtres.data && filtres.data.divisions.length > 1 && (
        <p className="mb-3 text-sm text-slate-600">{filtres.data.divisions.length} divisions dans votre périmètre — utilisez le filtre « Division » pour vous concentrer sur l'une d'elles.</p>
      )}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-52 flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-600" aria-hidden />
          <input className="input pl-9" type="search" placeholder="Rechercher par titre ou nom de fichier…" aria-label="Rechercher un fichier" value={q}
            onChange={(e) => { setQ(e.target.value); setParam('q', e.target.value || null) }} />
        </div>
        <select className="input w-auto" aria-label="Affecté à" value={params.get('agent') ?? ''} onChange={(e) => setParam('agent', e.target.value || null)}>
          <option value="">Tous les agents affectés</option>
          {(filtres.data?.agents ?? []).map((x) => <option key={x.id} value={x.id}>{x.prenom} {x.nom}{x.division_nom ? ` · ${x.division_nom}` : ''}</option>)}
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
        <div className="flex gap-1 rounded-lg border border-line p-0.5" role="tablist">
          <button role="tab" aria-selected={!corbeille} className={`rounded-md px-3 py-1 text-sm ${!corbeille ? 'bg-navy-700 font-semibold text-white' : 'text-black hover:bg-navy-100'}`} onClick={() => setParam('vue', null)}>Fichiers</button>
          <button role="tab" aria-selected={corbeille} className={`rounded-md px-3 py-1 text-sm ${corbeille ? 'bg-navy-700 font-semibold text-white' : 'text-black hover:bg-navy-100'}`} onClick={() => setParam('vue', 'corbeille')}>Corbeille</button>
          <button role="tab" aria-selected={filters.a_affecter} className={`rounded-md px-3 py-1 text-sm ${filters.a_affecter ? 'bg-navy-700 font-semibold text-white' : 'text-black hover:bg-navy-100'}`} onClick={() => setParam('a_affecter', filters.a_affecter ? null : '1')}>À affecter</button>
        </div>
        {chosen.length > 0 && !corbeille && (
          <div className="flex items-center gap-2 text-sm text-slate-600">
            {plural(chosen.length, 'fichier sélectionné', 'fichiers sélectionnés')}
            <button className="btn-ghost" onClick={() => setDialog({ kind: 'classify-many' })}><Tags className="h-4 w-4" /> Métadonnées</button>
          </div>
        )}
      </div>
      {agentChoisi && <p className="mb-3 text-sm text-slate-600">Filtré par affectation : <Badge tone="green">{agentChoisi.prenom} {agentChoisi.nom}{agentChoisi.division_nom ? ` · ${agentChoisi.division_nom}` : ''}</Badge> — seuls les fichiers affectés à cet agent (et accessibles avec vos droits) apparaissent.</p>}

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
                {!corbeille && <th className="th w-8"><input type="checkbox" aria-label="Tout sélectionner" className="accent-navy-700" checked={allSelected} onChange={() => setSelected(allSelected ? new Set() : new Set(items.map((i) => i.id)))} /></th>}
                <th className="th">Fichier</th><th className="th">Division</th><th className="th">Affectations</th><th className="th">Métadonnées</th><th className="th">Statut</th><th className="th">Modifié</th><th className="th text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((doc) => (
                <tr key={doc.id} className={selected.has(doc.id) ? 'bg-navy-50' : 'hover:bg-slate-50'}>
                  {!corbeille && <td className="td"><input type="checkbox" aria-label={`Sélectionner ${doc.titre}`} className="accent-navy-700" checked={selected.has(doc.id)} onChange={() => toggle(doc.id)} /></td>}
                  <td className="td min-w-56">
                    <Link to={`/fichiers/${doc.id}`} className="font-medium text-black hover:text-navy-600">{doc.titre}</Link>
                    <p className="text-xs text-slate-600">{doc.version.nom_fichier} · {formatSize(doc.version.taille_octets)}{doc.version.nb_pages ? ` · ${doc.version.nb_pages} p.` : ''}{doc.version.ocr_utilise ? ' · OCR' : ''}</p>
                    <p className="text-xs text-slate-600">v{doc.version.numero} · {plural(doc.nb_versions, 'version')}</p>
                  </td>
                  <td className="td text-sm text-slate-800">{doc.division_nom}</td>
                  <td className="td"><AffectationBadges doc={doc} /></td>
                  <td className="td"><ClassementBadges doc={doc} /></td>
                  <td className="td">
                    <StatusBadge statut={doc.version.statut} />
                    {doc.version.statut === 'error' && doc.version.message_erreur && <p className="mt-1 max-w-48 text-xs text-red-700">{doc.version.message_erreur}</p>}
                  </td>
                  <td className="td whitespace-nowrap text-xs text-slate-600">{formatDate(doc.modifie_le)}<br />{doc.cree_par_nom ?? ''}</td>
                  <td className="td">
                    <div className="flex justify-end gap-0.5">
                      {corbeille ? (
                        <>
                          {doc.droits.includes('supprimer') && <button className="btn-icon" title="Restaurer" aria-label={`Restaurer ${doc.titre}`} onClick={() => void mutations.restore.mutateAsync(doc.id).then(() => toast.success('Fichier restauré.')).catch((e) => toast.error(errorMessage(e)))}><RotateCcw className="h-4 w-4" /></button>}
                          {doc.droits.includes('purger') && <button className="btn-icon text-red-600" title="Supprimer définitivement" aria-label={`Supprimer définitivement ${doc.titre}`} onClick={() => setDialog({ kind: 'purge', doc })}><Trash2 className="h-4 w-4" /></button>}
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
                          {doc.droits.includes('classer') && <button className="btn-icon" title="Métadonnées" aria-label={`Métadonnées de ${doc.titre}`} onClick={() => setDialog({ kind: 'classify', doc })}><Tags className="h-4 w-4" /></button>}
                          {doc.droits.includes('affecter') && <button className="btn-icon" title="Affecter à des agents" aria-label={`Affecter ${doc.titre}`} onClick={() => setDialog({ kind: 'affect', doc })}><UserSquare className="h-4 w-4" /></button>}
                          {doc.droits.includes('supprimer') && <button className="btn-icon text-red-600" title="Mettre à la corbeille" aria-label={`Supprimer ${doc.titre}`} onClick={() => setDialog({ kind: 'trash', doc })}><Trash2 className="h-4 w-4" /></button>}
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
      {corbeille && <p className="mt-3 text-xs text-slate-600"><Badge tone="gray">Info</Badge> Les fichiers de la corbeille ne sont plus visibles dans la liste ni interrogés par l’assistant.</p>}

      {dialog?.kind === 'add' && <AddDocumentModal divisions={divisionsDepot} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'edit' && <EditDocumentModal doc={dialog.doc} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'version' && <NewVersionModal doc={dialog.doc} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'classify' && <ClassifyModal docs={[dialog.doc]} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'affect' && <AffectationModal doc={dialog.doc} onClose={() => setDialog(null)} />}
      {dialog?.kind === 'classify-many' && <ClassifyModal docs={chosen} onClose={() => setDialog(null)} onDone={() => setSelected(new Set())} />}
      {dialog?.kind === 'trash' && (
        <ConfirmDialog title="Mettre à la corbeille" confirmLabel="Mettre à la corbeille" onClose={() => setDialog(null)}
          onConfirm={async () => { await mutations.remove.mutateAsync(dialog.doc.id); toast.success('Fichier placé dans la corbeille.') }}>
          Mettre <span className="font-semibold text-navy-600">« {dialog.doc.titre} »</span> dans la corbeille ? Il ne sera plus visible ni interrogé par l’assistant, mais pourra être restauré.
        </ConfirmDialog>
      )}
      {dialog?.kind === 'purge' && (
        <ConfirmDialog title="Supprimer définitivement" confirmLabel="Supprimer définitivement" onClose={() => setDialog(null)}
          onConfirm={async () => { await mutations.purge.mutateAsync(dialog.doc.id); toast.success('Fichier supprimé définitivement.') }}>
          Supprimer définitivement <span className="font-semibold text-navy-600">« {dialog.doc.titre} »</span>, toutes ses versions et leurs passages indexés ? Cette action est irréversible.
        </ConfirmDialog>
      )}
    </>
  )
}
