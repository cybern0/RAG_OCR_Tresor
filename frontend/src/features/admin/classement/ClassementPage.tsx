// Référentiel de classement : catégories, types, étiquettes, règles automatiques et simulation d'une règle sur un fichier fictif.
import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { cn } from '../../../shared/lib/cn'
import Badge from '../../../shared/ui/Badge'
import ConfirmDialog from '../../../shared/ui/ConfirmDialog'
import Field from '../../../shared/ui/Field'
import { EmptyState, ErrorBox, Loading } from '../../../shared/ui/Feedback'
import Modal from '../../../shared/ui/Modal'
import PageHeader from '../../../shared/ui/PageHeader'
import { useToast } from '../../../shared/hooks/useToast'
import * as api from '../api'
import { adminKeys, useAdminMutation, useCategories, useRules, useTags, useTypes } from '../queries'
import type { RuleItem, SimulationResult } from '../types'

const TABS = [['categories', 'Catégories'], ['types', 'Types'], ['tags', 'Étiquettes'], ['regles', 'Règles automatiques'], ['simulation', 'Simulation']] as const
type Tab = (typeof TABS)[number][0]

function AddLine({ placeholder, onAdd, extra }: { placeholder: string; onAdd: (nom: string) => Promise<unknown>; extra?: React.ReactNode }) {
  const [nom, setNom] = useState('')
  const [error, setError] = useState<string | null>(null)
  async function submit(e: FormEvent) { e.preventDefault(); setError(null); try { await onAdd(nom.trim()); setNom('') } catch (err) { setError(errorMessage(err)) } }
  return (
    <form onSubmit={(e) => void submit(e)} className="mb-3 flex flex-wrap gap-2">
      <input className="input min-w-48 flex-1" required maxLength={100} aria-label={placeholder} placeholder={placeholder} value={nom} onChange={(e) => setNom(e.target.value)} />
      {extra}
      <button className="btn"><Plus className="h-4 w-4" /> Ajouter</button>
      <ErrorBox message={error} className="w-full" />
    </form>
  )
}

function Row({ children, onDelete, label }: { children: React.ReactNode; onDelete: () => Promise<unknown>; label: string }) {
  const toast = useToast()
  const [confirm, setConfirm] = useState(false)
  return (
    <li className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2">
      <div className="flex min-w-0 flex-1 items-center gap-2">{children}</div>
      <button className="btn-icon text-red-600" aria-label={`Supprimer ${label}`} onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" /></button>
      {confirm && <ConfirmDialog title="Supprimer" confirmLabel="Supprimer" onClose={() => setConfirm(false)} onConfirm={async () => { await onDelete(); toast.success('Supprimé.') }}>Supprimer « {label} » ? Les fichiers déjà classés perdent cette valeur.</ConfirmDialog>}
    </li>
  )
}

function Categories() {
  const cats = useCategories()
  const [couleur, setCouleur] = useState('#173f78')
  const create = useAdminMutation((v: { nom: string }) => api.createCategory({ nom: v.nom, couleur }), [adminKeys.categories])
  const update = useAdminMutation((v: { id: number; actif: boolean }) => api.updateCategory(v.id, { actif: v.actif }), [adminKeys.categories])
  const remove = useAdminMutation(api.deleteCategory, [adminKeys.categories])
  const toast = useToast()
  return (
    <>
      <AddLine placeholder="Nouvelle catégorie" onAdd={(nom) => create.mutateAsync({ nom })}
        extra={<input type="color" aria-label="Couleur" className="h-10 w-12 cursor-pointer rounded-lg border border-line bg-white p-1" value={couleur} onChange={(e) => setCouleur(e.target.value)} />} />
      {cats.isPending ? <Loading /> : (cats.data ?? []).length === 0 ? <p className="text-sm text-slate-600">Aucune catégorie.</p> : (
        <ul className="space-y-2">{cats.data!.map((c) => (
          <Row key={c.id} label={c.nom} onDelete={() => remove.mutateAsync(c.id)}>
            <span className="h-3.5 w-3.5 shrink-0 rounded-full" style={{ background: c.couleur ?? 'var(--color-navy-700)' }} />
            <span className="truncate text-sm">{c.nom}</span>
            <button className="ml-auto" onClick={() => void update.mutateAsync({ id: c.id, actif: !c.actif }).catch((e) => toast.error(errorMessage(e)))}><Badge tone={c.actif ? 'green' : 'gray'}>{c.actif ? 'Active' : 'Désactivée'}</Badge></button>
          </Row>
        ))}</ul>
      )}
    </>
  )
}

function Types() {
  const types = useTypes()
  const create = useAdminMutation((v: { nom: string }) => api.createType(v), [adminKeys.types])
  const update = useAdminMutation((v: { id: number; actif: boolean }) => api.updateType(v.id, { actif: v.actif }), [adminKeys.types])
  const remove = useAdminMutation(api.deleteType, [adminKeys.types])
  const toast = useToast()
  return (
    <>
      <AddLine placeholder="Nouveau type (ex. Facture)" onAdd={(nom) => create.mutateAsync({ nom })} />
      {types.isPending ? <Loading /> : (types.data ?? []).length === 0 ? <p className="text-sm text-slate-600">Aucun type.</p> : (
        <ul className="space-y-2">{types.data!.map((t) => (
          <Row key={t.id} label={t.nom} onDelete={() => remove.mutateAsync(t.id)}>
            <span className="truncate text-sm">{t.nom}</span>
            <button className="ml-auto" onClick={() => void update.mutateAsync({ id: t.id, actif: !t.actif }).catch((e) => toast.error(errorMessage(e)))}><Badge tone={t.actif ? 'green' : 'gray'}>{t.actif ? 'Actif' : 'Désactivé'}</Badge></button>
          </Row>
        ))}</ul>
      )}
    </>
  )
}

function Tags() {
  const tags = useTags()
  const create = useAdminMutation((v: { nom: string }) => api.createTag(v), [adminKeys.tags])
  const remove = useAdminMutation(api.deleteTag, [adminKeys.tags])
  return (
    <>
      <AddLine placeholder="Nouvelle étiquette" onAdd={(nom) => create.mutateAsync({ nom })} />
      {tags.isPending ? <Loading /> : (tags.data ?? []).length === 0 ? <p className="text-sm text-slate-600">Aucune étiquette.</p> : (
        <ul className="grid gap-2 sm:grid-cols-2">{tags.data!.map((t) => <Row key={t.id} label={t.nom} onDelete={() => remove.mutateAsync(t.id)}><span className="truncate text-sm">#{t.nom}</span></Row>)}</ul>
      )}
    </>
  )
}

const CRITERE_EXEMPLE = '[\n  { "champ": "extension", "op": "=", "valeur": "pdf" },\n  { "champ": "texte", "op": "contient_un_de", "valeur": ["facture", "montant"] }\n]'

function RuleModal({ target, onClose }: { target: RuleItem | null; onClose: () => void }) {
  const toast = useToast()
  const cats = useCategories()
  const types = useTypes()
  const [nom, setNom] = useState(target?.nom ?? '')
  const [priorite, setPriorite] = useState(target?.priorite ?? 100)
  const [critere, setCritere] = useState(target ? JSON.stringify(target.critere, null, 2) : CRITERE_EXEMPLE)
  const [categorie, setCategorie] = useState<number | ''>(target?.categorie_id ?? '')
  const [type, setType] = useState<number | ''>(target?.type_document_id ?? '')
  const [tags, setTags] = useState(target?.tags.join(', ') ?? '')
  const [conf, setConf] = useState(target?.confidentialite ?? '')
  const [error, setError] = useState<string | null>(null)
  const save = useAdminMutation((payload: api.RuleInput) => target ? api.updateRule(target.id, payload) : api.createRule(payload), [adminKeys.rules])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    let parsed: unknown
    try { parsed = JSON.parse(critere) } catch { return setError('Les critères ne sont pas un JSON valide.') }
    try {
      await save.mutateAsync({ nom, priorite, critere: parsed, categorie_id: categorie || null, type_document_id: type || null, tags: tags.split(/[;,]+/).map((t) => t.trim()).filter(Boolean), confidentialite: conf || null })
      toast.success(target ? 'Règle modifiée.' : 'Règle créée.')
      onClose()
    } catch (err) { setError(errorMessage(err)) }
  }

  return (
    <Modal title={target ? 'Modifier la règle' : 'Nouvelle règle'} onClose={onClose} size="lg">
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
          <Field label="Nom">{(id) => <input id={id} className="input" required value={nom} onChange={(e) => setNom(e.target.value)} />}</Field>
          <Field label="Priorité" hint="Plus petit = plus tôt.">{(id) => <input id={id} type="number" min={0} className="input" value={priorite} onChange={(e) => setPriorite(Number(e.target.value))} />}</Field>
        </div>
        <Field label="Critères (JSON)" hint="Tous les critères doivent être vrais. Champs : texte, nom_fichier, extension. Opérateurs : =, dans, contient_un_de, regex.">
          {(id) => <textarea id={id} className="input min-h-32 font-mono text-xs" spellCheck={false} value={critere} onChange={(e) => setCritere(e.target.value)} />}
        </Field>
        <p className="text-xs text-slate-600">Si les critères sont vrais, le fichier reçoit :</p>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Catégorie">{(id) => <select id={id} className="input" value={categorie} onChange={(e) => setCategorie(e.target.value ? Number(e.target.value) : '')}><option value="">—</option>{cats.data?.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}</select>}</Field>
          <Field label="Type">{(id) => <select id={id} className="input" value={type} onChange={(e) => setType(e.target.value ? Number(e.target.value) : '')}><option value="">—</option>{types.data?.map((t) => <option key={t.id} value={t.id}>{t.nom}</option>)}</select>}</Field>
          <Field label="Confidentialité">{(id) => <select id={id} className="input" value={conf} onChange={(e) => setConf(e.target.value)}><option value="">—</option><option value="PUBLIC">Public</option><option value="INTERNE">Interne</option><option value="CONFIDENTIEL">Confidentiel</option></select>}</Field>
        </div>
        <Field label="Étiquettes" hint="Séparées par des virgules.">{(id) => <input id={id} className="input" value={tags} onChange={(e) => setTags(e.target.value)} />}</Field>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={onClose}>Annuler</button><button className="btn" disabled={save.isPending}>{target ? 'Enregistrer' : 'Créer'}</button></div>
      </form>
    </Modal>
  )
}

function Rules() {
  const rules = useRules()
  const toast = useToast()
  const [modal, setModal] = useState<{ target: RuleItem | null } | null>(null)
  const toggle = useAdminMutation((v: { id: number; actif: boolean }) => api.updateRule(v.id, { actif: v.actif }), [adminKeys.rules])
  const remove = useAdminMutation(api.deleteRule, [adminKeys.rules])
  return (
    <>
      <div className="mb-3 flex justify-between gap-2"><p className="text-sm text-slate-600">Appliquées à l’indexation, par ordre de priorité. Un classement manuel n’est jamais écrasé.</p><button className="btn shrink-0" onClick={() => setModal({ target: null })}><Plus className="h-4 w-4" /> Règle</button></div>
      {rules.isPending ? <Loading /> : (rules.data ?? []).length === 0 ? <EmptyState title="Aucune règle" /> : (
        <ul className="space-y-2">{rules.data!.map((r) => (
          <Row key={r.id} label={r.nom} onDelete={() => remove.mutateAsync(r.id)}>
            <button className="min-w-0 flex-1 text-left" onClick={() => setModal({ target: r })}><span className="block truncate text-sm font-medium hover:text-navy-600">{r.nom}</span><span className="text-xs text-slate-600">Priorité {r.priorite}{r.confidentialite ? ` · ${r.confidentialite}` : ''}{r.tags.length ? ` · ${r.tags.map((t) => '#' + t).join(' ')}` : ''}</span></button>
            <button onClick={() => void toggle.mutateAsync({ id: r.id, actif: !r.actif }).catch((e) => toast.error(errorMessage(e)))}><Badge tone={r.actif ? 'green' : 'gray'}>{r.actif ? 'Active' : 'Inactive'}</Badge></button>
          </Row>
        ))}</ul>
      )}
      {modal && <RuleModal target={modal.target} onClose={() => setModal(null)} />}
    </>
  )
}

function Simulation() {
  const cats = useCategories()
  const types = useTypes()
  const [nomFichier, setNomFichier] = useState('facture-2026.pdf')
  const [texte, setTexte] = useState('Facture n° 124 — montant à payer : 120 000 Ar')
  const [result, setResult] = useState<SimulationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const run = useAdminMutation(() => api.simulate({ nom_fichier: nomFichier, extension: nomFichier.split('.').pop(), texte }), [])
  async function submit(e: FormEvent) { e.preventDefault(); setError(null); try { setResult(await run.mutateAsync(undefined)) } catch (err) { setError(errorMessage(err)) } }
  return (
    <form onSubmit={(e) => void submit(e)} className="max-w-xl space-y-4">
      <p className="text-sm text-slate-600">Teste les règles actives sur un fichier fictif, sans rien enregistrer.</p>
      <Field label="Nom du fichier">{(id) => <input id={id} className="input" value={nomFichier} onChange={(e) => setNomFichier(e.target.value)} />}</Field>
      <Field label="Extrait du texte">{(id) => <textarea id={id} className="input min-h-24" value={texte} onChange={(e) => setTexte(e.target.value)} />}</Field>
      <ErrorBox message={error} />
      <button className="btn" disabled={run.isPending}>Simuler</button>
      {result && (
        <div className="card space-y-1 p-4 text-sm" role="status">
          <p>Catégorie : <b className="text-navy-600">{cats.data?.find((c) => c.id === result.categorie_id)?.nom ?? 'aucune'}</b></p>
          <p>Type : <b className="text-navy-600">{types.data?.find((t) => t.id === result.type_document_id)?.nom ?? 'aucun'}</b></p>
          <p>Confidentialité : <b className="text-navy-600">{result.confidentialite ?? 'inchangée'}</b></p>
          <p>Étiquettes : <b className="text-navy-600">{result.tags.length ? result.tags.map((t) => '#' + t).join(' ') : 'aucune'}</b></p>
        </div>
      )}
    </form>
  )
}

export function Component() {
  const [tab, setTab] = useState<Tab>('categories')
  return (
    <>
      <PageHeader title="Classement" description="Catégories, types, étiquettes et règles qui classent automatiquement les fichiers à l’indexation." />
      <div className="mb-4 flex flex-wrap gap-1 border-b border-line" role="tablist">
        {TABS.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
            className={cn('-mb-px border-b-2 px-4 py-2 text-sm font-medium transition', tab === id ? 'border-navy-600 text-navy-600' : 'border-transparent text-black hover:text-navy-600')}>{label}</button>
        ))}
      </div>
      <div className="max-w-3xl" role="tabpanel">
        {tab === 'categories' && <Categories />}{tab === 'types' && <Types />}{tab === 'tags' && <Tags />}{tab === 'regles' && <Rules />}{tab === 'simulation' && <Simulation />}
      </div>
    </>
  )
}
