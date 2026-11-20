import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  createCategory,
  createRule,
  createTag,
  createType,
  deleteCategory,
  deleteRule,
  deleteTag,
  deleteType,
  fetchDashboardStats,
  listCategories,
  listRules,
  listTags,
  listTypes,
  simulateClassification,
  type CategoryItem,
  type RuleItem,
  type TagItem,
  type TypeItem,
  updateCategory,
  updateRule,
  updateTag,
  updateType,
} from '../../api/classement'
import { ErrorBox, Loading } from '../../components/ui/Feedback'
import { getAcces, listDossiers } from '../../api/dossiers'
import { createDocumentLinkShare, listAccessRequests, listDocuments, resolveAccessRequest, type AccessRequestItem } from '../../api/documents'
import { useLoad } from '../../hooks/useLoad'
import { errorMessage } from '../../api/client'
import type { AccesDossier, Dossier } from '../../types/dossier'

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="card p-4">
      <div className="text-xs uppercase tracking-wide text-slate-600">{label}</div>
      <div className="mt-3 text-2xl font-bold text-navy-700">{value}</div>
    </div>
  )
}

function ListMetrics({ title, items }: { title: string; items: Array<{ label: string; value: number }> }) {
  const total = Math.max(items.reduce((sum, item) => sum + item.value, 0), 1)

  return (
    <div className="card p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">{title}</h3>
      <div className="space-y-3">
        {items.length === 0 && <p className="text-sm text-slate-600">Aucune donnée.</p>}
        {items.map((item) => (
          <div key={item.label}>
            <div className="mb-1 flex items-center justify-between gap-3 text-sm text-black">
              <span className="truncate">{item.label}</span>
              <span className="font-medium text-navy-600">{item.value}</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-navy-700" style={{ width: `${(item.value / total) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function LabelValue({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="rounded-lg border border-line bg-slate-50 p-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-600">{label}</div>
      <div className="mt-1 text-sm font-medium text-black">{value ?? '—'}</div>
    </div>
  )
}

export default function GedDashboardPanel() {
  const [tab, setTab] = useState<'dashboard' | 'gestion' | 'partage'>('dashboard')
  const stats = useLoad(fetchDashboardStats)
  const categories = useLoad(listCategories)
  const types = useLoad(listTypes)
  const tags = useLoad(listTags)
  const rules = useLoad(listRules)
  const dossiers = useLoad(listDossiers)
  const documents = useLoad(listDocuments)
  const accessRequests = useLoad(() => listAccessRequests({ status: 'pending' }))
  const [accessByDossier, setAccessByDossier] = useState<Record<number, AccesDossier>>({})
  const [generatedLinks, setGeneratedLinks] = useState<Record<number, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [categoryForm, setCategoryForm] = useState({ nom: '', couleur: '#173f78', ordre: '0', actif: true })
  const [typeForm, setTypeForm] = useState({ nom: '', actif: true })
  const [tagForm, setTagForm] = useState({ nom: '' })
  const [ruleForm, setRuleForm] = useState({
    nom: '',
    priorite: '100',
    actif: true,
    categorie_id: '',
    type_document_id: '',
    confidentialite: '',
    tags: '',
    critere: '{\n  "tous": [\n    { "champ": "extension", "op": "dans", "valeur": ["pdf"] }\n  ]\n}',
  })
  const [simulation, setSimulation] = useState<null | { categorie_id: number | null; type_document_id: number | null; tags: string[]; confidentialite: string | null }>(null)

  useEffect(() => {
    if (!dossiers.data?.length) return
    let active = true
    Promise.all(
      dossiers.data.map(async (dossier: Dossier) => ({ id: dossier.id, access: await getAcces(dossier.id) })),
    )
      .then((entries) => {
        if (!active) return
        setAccessByDossier(Object.fromEntries(entries.map((entry) => [entry.id, entry.access])))
      })
      .catch((err) => {
        if (active) setError(errorMessage(err))
      })
    return () => { active = false }
  }, [dossiers.data])

  async function refreshMetadata() {
    await Promise.all([categories.reload(), types.reload(), tags.reload(), rules.reload()])
  }

  async function submitCategory(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await createCategory({
        nom: categoryForm.nom.trim(),
        parent_id: null,
        couleur: categoryForm.couleur || null,
        ordre: Number(categoryForm.ordre || 0),
        actif: categoryForm.actif,
      })
      setCategoryForm({ nom: '', couleur: '#173f78', ordre: '0', actif: true })
      await refreshMetadata()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function submitType(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await createType({ nom: typeForm.nom.trim(), actif: typeForm.actif })
      setTypeForm({ nom: '', actif: true })
      await refreshMetadata()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function submitTag(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await createTag({ nom: tagForm.nom.trim() })
      setTagForm({ nom: '' })
      await refreshMetadata()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function submitRule(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const parsed = JSON.parse(ruleForm.critere || '{}')
      await createRule({
        nom: ruleForm.nom.trim(),
        priorite: Number(ruleForm.priorite || 100),
        actif: ruleForm.actif,
        critere: typeof parsed === 'object' && parsed ? parsed : {},
        categorie_id: ruleForm.categorie_id ? Number(ruleForm.categorie_id) : null,
        type_document_id: ruleForm.type_document_id ? Number(ruleForm.type_document_id) : null,
        confidentialite: ruleForm.confidentialite || null,
        tags: ruleForm.tags.split(/[;,\n]+/).map((tag) => tag.trim()).filter(Boolean),
      })
      setRuleForm({
        nom: '',
        priorite: '100',
        actif: true,
        categorie_id: '',
        type_document_id: '',
        confidentialite: '',
        tags: '',
        critere: '{\n  "tous": [\n    { "champ": "extension", "op": "dans", "valeur": ["pdf"] }\n  ]\n}',
      })
      await refreshMetadata()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function handleSimulation() {
    setError(null)
    try {
      const result = await simulateClassification({
        nom_fichier: 'FAC-2026-0001.pdf',
        extension: 'pdf',
        dossier_id: dossiers.data?.[0]?.id,
        texte: 'Décret de publication et facturation administrative',
        taille_octets: 418_000,
        nb_pages: 3,
        ocr_utilise: false,
      })
      setSimulation(result)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function createShareLink(documentId: number) {
    setError(null)
    try {
      const created = await createDocumentLinkShare(documentId, { role: 'LECTEUR', est_anonyme: true })
      if (created.token) {
        setGeneratedLinks((prev) => ({ ...prev, [documentId]: created.token ?? '' }))
      }
      await accessRequests.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function decideAccessRequest(requestId: number, decision: 'accepted' | 'rejected') {
    setError(null)
    try {
      await resolveAccessRequest(requestId, { decision, granted_role: decision === 'accepted' ? 'LECTEUR' : null, message: decision === 'accepted' ? 'Demande acceptée localement par l’administrateur.' : 'Demande refusée localement.' })
      await accessRequests.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function copyShareToken(token: string) {
    if (!token) return
    try {
      await navigator.clipboard.writeText(token)
    } catch {
      window.prompt('Copier le jeton de partage local', token)
    }
  }

  async function toggleCategory(item: CategoryItem) {
    setError(null)
    try {
      await updateCategory(item.id, { actif: !item.actif })
      await categories.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function removeCategory(item: CategoryItem) {
    if (!window.confirm(`Désactiver la catégorie « ${item.nom} » ?`)) return
    setError(null)
    try {
      await deleteCategory(item.id)
      await categories.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function renameCategory(item: CategoryItem) {
    const next = window.prompt('Nouveau nom de catégorie', item.nom)
    if (!next || !next.trim()) return
    setError(null)
    try {
      await updateCategory(item.id, { nom: next.trim() })
      await categories.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function toggleType(item: TypeItem) {
    setError(null)
    try {
      await updateType(item.id, { actif: !item.actif })
      await types.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function renameType(item: TypeItem) {
    const next = window.prompt('Nouveau nom de type', item.nom)
    if (!next || !next.trim()) return
    setError(null)
    try {
      await updateType(item.id, { nom: next.trim() })
      await types.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function removeType(item: TypeItem) {
    if (!window.confirm(`Désactiver le type « ${item.nom} » ?`)) return
    setError(null)
    try {
      await deleteType(item.id)
      await types.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function renameTag(item: TagItem) {
    const next = window.prompt('Nouveau nom du tag', item.nom)
    if (!next || !next.trim()) return
    setError(null)
    try {
      await updateTag(item.id, { nom: next.trim() })
      await tags.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function removeTag(item: TagItem) {
    if (!window.confirm(`Supprimer le tag « ${item.nom} » ?`)) return
    setError(null)
    try {
      await deleteTag(item.id)
      await tags.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function toggleRule(item: RuleItem) {
    setError(null)
    try {
      await updateRule(item.id, { actif: !item.actif })
      await rules.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function removeRule(item: RuleItem) {
    if (!window.confirm(`Supprimer la règle « ${item.nom} » ?`)) return
    setError(null)
    try {
      await deleteRule(item.id)
      await rules.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (stats.loading || categories.loading || types.loading || tags.loading || rules.loading || dossiers.loading || documents.loading || accessRequests.loading) {
    return <Loading />
  }
  if (stats.error) return <ErrorBox message={stats.error} />

  const data = stats.data
  if (!data) return null

  const statusEntries = Object.entries(data.statut ?? {}).map(([label, value]) => ({ label, value: Number(value) }))
  const confidentialityEntries = Object.entries(data.par_confidentialite ?? {}).map(([label, value]) => ({ label, value: Number(value) }))
  const extensionEntries = Object.entries(data.par_extension ?? {}).map(([label, value]) => ({ label, value: Number(value) }))
  const categoryEntries = (data.par_categorie ?? []).map((item) => ({ label: `Catégorie #${item.categorie_id ?? 'n/a'}`, value: item.total }))
  const typeEntries = (data.par_type ?? []).map((item) => ({ label: `Type #${item.type_document_id ?? 'n/a'}`, value: item.total }))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" role="tablist">
        <button className={tab === 'dashboard' ? 'btn' : 'btn-ghost'} onClick={() => setTab('dashboard')}>Dashboard</button>
        <button className={tab === 'gestion' ? 'btn' : 'btn-ghost'} onClick={() => setTab('gestion')}>Gestion GED</button>
        <button className={tab === 'partage' ? 'btn' : 'btn-ghost'} onClick={() => setTab('partage')}>Partage et collaboration</button>
      </div>

      <ErrorBox message={error} />

      {tab === 'dashboard' && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Documents" value={data.total_documents} />
            <StatCard label="Actifs" value={data.actifs} />
            <StatCard label="Corbeille" value={data.corbeille} />
            <StatCard label="États" value={Object.values(data.statut ?? {}).reduce((sum, value) => sum + Number(value), 0)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ListMetrics title="Par statut" items={statusEntries} />
            <ListMetrics title="Par confidentialité" items={confidentialityEntries} />
            <ListMetrics title="Par catégorie" items={categoryEntries} />
            <ListMetrics title="Par type" items={typeEntries} />
            <ListMetrics title="Par extension" items={extensionEntries} />
            <div className="card p-4">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">Services / directions</h3>
              <div className="space-y-3 text-sm text-black">
                {(data.par_service ?? []).map((item) => (
                  <div key={item.service_id} className="flex items-center justify-between gap-3">
                    <span>Service #{item.service_id}</span>
                    <span className="font-medium text-navy-600">{item.total}</span>
                  </div>
                ))}
                {(data.par_direction ?? []).map((item) => (
                  <div key={item.direction_id} className="flex items-center justify-between gap-3">
                    <span>Direction #{item.direction_id}</span>
                    <span className="font-medium text-navy-600">{item.total}</span>
                  </div>
                ))}
                {(!data.par_service?.length && !data.par_direction?.length) && <p className="text-slate-600">Aucune donnée de service ou de direction.</p>}
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'gestion' && (
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="card p-4">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">Catégories</h3>
            <form className="space-y-3" onSubmit={(e) => void submitCategory(e)}>
              <div><label className="label" htmlFor="cat-nom">Nom</label><input id="cat-nom" className="input" value={categoryForm.nom} onChange={(e) => setCategoryForm({ ...categoryForm, nom: e.target.value })} required /></div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div><label className="label" htmlFor="cat-couleur">Couleur</label><input id="cat-couleur" type="color" className="input h-10 px-2" value={categoryForm.couleur} onChange={(e) => setCategoryForm({ ...categoryForm, couleur: e.target.value })} /></div>
                <div><label className="label" htmlFor="cat-ordre">Ordre</label><input id="cat-ordre" type="number" className="input" value={categoryForm.ordre} onChange={(e) => setCategoryForm({ ...categoryForm, ordre: e.target.value })} /></div>
              </div>
              <label className="flex items-center gap-2 text-sm text-black"><input type="checkbox" checked={categoryForm.actif} onChange={(e) => setCategoryForm({ ...categoryForm, actif: e.target.checked })} /> Actif</label>
              <button className="btn" type="submit">Ajouter</button>
            </form>
            <div className="mt-4 space-y-2">
              {(categories.data ?? []).map((item: CategoryItem) => (
                <div key={item.id} className="flex flex-col gap-2 rounded-lg border border-line bg-slate-50 p-2 text-sm md:flex-row md:items-center md:justify-between">
                  <span className="flex items-center gap-2"><span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: item.couleur ?? '#173f78' }} /> {item.nom}</span>
                  <span className="text-slate-600">{item.actif ? 'Actif' : 'Inactif'}</span>
                  <div className="flex gap-2">
                    <button type="button" className="btn-ghost" onClick={() => void renameCategory(item)}>Renommer</button>
                    <button type="button" className="btn-ghost" onClick={() => void toggleCategory(item)}>{item.actif ? 'Désactiver' : 'Réactiver'}</button>
                    <button type="button" className="btn-danger" onClick={() => void removeCategory(item)}>Supprimer</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card p-4">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">Types de document</h3>
            <form className="space-y-3" onSubmit={(e) => void submitType(e)}>
              <div><label className="label" htmlFor="type-nom">Nom</label><input id="type-nom" className="input" value={typeForm.nom} onChange={(e) => setTypeForm({ ...typeForm, nom: e.target.value })} required /></div>
              <label className="flex items-center gap-2 text-sm text-black"><input type="checkbox" checked={typeForm.actif} onChange={(e) => setTypeForm({ ...typeForm, actif: e.target.checked })} /> Actif</label>
              <button className="btn" type="submit">Ajouter</button>
            </form>
            <div className="mt-4 space-y-2">
              {(types.data ?? []).map((item: TypeItem) => (
                <div key={item.id} className="flex flex-col gap-2 rounded-lg border border-line bg-slate-50 p-2 text-sm md:flex-row md:items-center md:justify-between">
                  <span>{item.nom}</span>
                  <span className="text-slate-600">{item.actif ? 'Actif' : 'Inactif'}</span>
                  <div className="flex gap-2">
                    <button type="button" className="btn-ghost" onClick={() => void renameType(item)}>Renommer</button>
                    <button type="button" className="btn-ghost" onClick={() => void toggleType(item)}>{item.actif ? 'Désactiver' : 'Réactiver'}</button>
                    <button type="button" className="btn-danger" onClick={() => void removeType(item)}>Supprimer</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card p-4">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">Tags</h3>
            <form className="space-y-3" onSubmit={(e) => void submitTag(e)}>
              <div><label className="label" htmlFor="tag-nom">Nom du tag</label><input id="tag-nom" className="input" value={tagForm.nom} onChange={(e) => setTagForm({ nom: e.target.value })} required /></div>
              <button className="btn" type="submit">Ajouter</button>
            </form>
            <div className="mt-4 flex flex-wrap gap-2">
              {(tags.data ?? []).map((item: TagItem) => (
                <span key={item.id} className="badge flex items-center gap-2 border-line bg-navy-50 text-navy-600">
                  {item.nom}
                  <button type="button" className="text-xs underline" onClick={() => void renameTag(item)}>✎</button>
                  <button type="button" className="text-xs underline" onClick={() => void removeTag(item)}>×</button>
                </span>
              ))}
            </div>
          </div>

          <div className="card p-4 xl:col-span-2">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">Règles de classement</h3>
            <form className="grid gap-3 md:grid-cols-2" onSubmit={(e) => void submitRule(e)}>
              <div className="md:col-span-2"><label className="label" htmlFor="rule-nom">Nom</label><input id="rule-nom" className="input" value={ruleForm.nom} onChange={(e) => setRuleForm({ ...ruleForm, nom: e.target.value })} required /></div>
              <div><label className="label" htmlFor="rule-prio">Priorité</label><input id="rule-prio" type="number" className="input" value={ruleForm.priorite} onChange={(e) => setRuleForm({ ...ruleForm, priorite: e.target.value })} /></div>
              <div><label className="label" htmlFor="rule-conf">Confidentialité</label><select id="rule-conf" className="input" value={ruleForm.confidentialite} onChange={(e) => setRuleForm({ ...ruleForm, confidentialite: e.target.value })}><option value="">Aucune</option><option value="PUBLIC">PUBLIC</option><option value="INTERNE">INTERNE</option><option value="CONFIDENTIEL">CONFIDENTIEL</option></select></div>
              <div><label className="label" htmlFor="rule-cat">Catégorie</label><select id="rule-cat" className="input" value={ruleForm.categorie_id} onChange={(e) => setRuleForm({ ...ruleForm, categorie_id: e.target.value })}><option value="">Aucune</option>{(categories.data ?? []).map((item: CategoryItem) => <option key={item.id} value={item.id}>{item.nom}</option>)}</select></div>
              <div><label className="label" htmlFor="rule-type">Type</label><select id="rule-type" className="input" value={ruleForm.type_document_id} onChange={(e) => setRuleForm({ ...ruleForm, type_document_id: e.target.value })}><option value="">Aucune</option>{(types.data ?? []).map((item: TypeItem) => <option key={item.id} value={item.id}>{item.nom}</option>)}</select></div>
              <div className="md:col-span-2"><label className="label" htmlFor="rule-tags">Tags</label><input id="rule-tags" className="input" value={ruleForm.tags} onChange={(e) => setRuleForm({ ...ruleForm, tags: e.target.value })} placeholder="finance, rh, dossier admin" /></div>
              <div className="md:col-span-2"><label className="label" htmlFor="rule-critere">Critère JSON</label><textarea id="rule-critere" className="input min-h-32" value={ruleForm.critere} onChange={(e) => setRuleForm({ ...ruleForm, critere: e.target.value })} /></div>
              <label className="md:col-span-2 flex items-center gap-2 text-sm text-black"><input type="checkbox" checked={ruleForm.actif} onChange={(e) => setRuleForm({ ...ruleForm, actif: e.target.checked })} /> Règle active</label>
              <div className="md:col-span-2 flex flex-wrap items-center gap-2">
                <button className="btn" type="submit">Créer</button>
                <button type="button" className="btn-ghost" onClick={() => void handleSimulation()}>Tester la règle</button>
              </div>
            </form>
            {simulation && (
              <div className="mt-4 rounded-lg border border-line bg-slate-50 p-3">
                <div className="mb-2 text-xs uppercase tracking-wide text-navy-700">Simulation</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <LabelValue label="Catégorie" value={simulation.categorie_id ?? '—'} />
                  <LabelValue label="Type" value={simulation.type_document_id ?? '—'} />
                  <LabelValue label="Confidentialité" value={simulation.confidentialite ?? '—'} />
                  <LabelValue label="Tags" value={simulation.tags.length ? simulation.tags.join(', ') : '—'} />
                </div>
              </div>
            )}
            <div className="mt-4 space-y-2">
              {(rules.data ?? []).map((item: RuleItem) => (
                <div key={item.id} className="rounded-lg border border-line bg-slate-50 p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-navy-600">{item.nom}</span>
                    <span className="text-slate-600">priorité {item.priorite}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {item.tags.map((tag) => <span key={`${item.id}-${tag}`} className="badge border-line bg-navy-50 text-navy-600">{tag}</span>)}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button type="button" className="btn-ghost" onClick={() => void toggleRule(item)}>{item.actif ? 'Désactiver' : 'Réactiver'}</button>
                    <button type="button" className="btn-danger" onClick={() => void removeRule(item)}>Supprimer</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === 'partage' && (
        <div className="space-y-4">
          <div className="card p-4">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-navy-700">Demandes d’accès en attente</h3>
            {(accessRequests.data ?? []).length === 0 && <p className="text-sm text-slate-600">Aucune demande en attente.</p>}
            <div className="space-y-3">
              {(accessRequests.data ?? []).map((request: AccessRequestItem) => (
                <div key={request.id} className="rounded-lg border border-line bg-slate-50 p-3">
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="text-sm font-medium text-navy-600">{request.subject_type === 'document' ? 'Document' : 'Dossier'} #{request.subject_id}</div>
                      <div className="text-xs text-slate-600">Demande de rôle {request.requested_role} · message : {request.message || '—'}</div>
                    </div>
                    <div className="flex gap-2">
                      <button type="button" className="btn-ghost" onClick={() => void decideAccessRequest(request.id, 'accepted')}>Accepter</button>
                      <button type="button" className="btn-danger" onClick={() => void decideAccessRequest(request.id, 'rejected')}>Refuser</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {(dossiers.data ?? []).map((dossier: Dossier) => {
            const access = accessByDossier[dossier.id]
            const dossierDocuments = (documents.data ?? []).filter((doc) => doc.dossier_id === dossier.id)
            return (
              <div key={dossier.id} className="card p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-navy-600">{dossier.nom}</h3>
                    <p className="text-sm text-slate-600">{dossier.nb_fichiers} document(s) · rôle actuel : {dossier.mon_role}</p>
                  </div>
                  <span className={`badge ${dossier.archive ? 'border-amber-300 bg-amber-50 text-amber-700' : 'border-green-300 bg-green-50 text-green-700'}`}>
                    {dossier.archive ? 'Archivé' : 'Actif'}
                  </span>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-lg border border-line bg-slate-50 p-3">
                    <div className="mb-2 text-xs uppercase tracking-wide text-navy-700">Membres</div>
                    <div className="space-y-2 text-sm text-black">
                      {(access?.membres ?? []).length === 0 && <p className="text-slate-600">Aucun accès direct.</p>}
                      {(access?.membres ?? []).map((member) => (
                        <div key={member.user_id} className="flex items-center justify-between gap-2">
                          <span>{member.nom_utilisateur}</span>
                          <span className="text-navy-600">{member.role}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-lg border border-line bg-slate-50 p-3">
                    <div className="mb-2 text-xs uppercase tracking-wide text-navy-700">Services</div>
                    <div className="space-y-2 text-sm text-black">
                      {(access?.services ?? []).length === 0 && <p className="text-slate-600">Aucun service autorisé.</p>}
                      {(access?.services ?? []).map((service) => (
                        <div key={service.service_id} className="flex items-center justify-between gap-2">
                          <span>{service.service_nom}</span>
                          <span className="text-navy-600">{service.role}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  <h4 className="text-sm font-semibold uppercase tracking-wide text-navy-700">Documents du dossier</h4>
                  {(dossierDocuments ?? []).length === 0 && <p className="text-sm text-slate-600">Aucun document.</p>}
                  {(dossierDocuments ?? []).map((doc) => (
                    <div key={doc.id} className="rounded-lg border border-line bg-slate-50 p-3">
                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <div>
                          <div className="font-medium text-navy-600">{doc.titre}</div>
                          <div className="text-xs text-slate-600">#{doc.id}</div>
                        </div>
                        <div className="flex gap-2">
                          <button type="button" className="btn-ghost" onClick={() => void createShareLink(doc.id)}>Créer lien</button>
                        </div>
                      </div>
                      {generatedLinks[doc.id] && (
                        <div className="mt-3 rounded border border-green-300 bg-green-50 p-2 text-sm text-green-800">
                          <div className="mb-1 text-xs uppercase tracking-wide text-green-700">Jeton de partage local</div>
                          <div className="break-all">{generatedLinks[doc.id]}</div>
                          <button type="button" className="mt-2 btn-ghost" onClick={() => void copyShareToken(generatedLinks[doc.id])}>Copier</button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
