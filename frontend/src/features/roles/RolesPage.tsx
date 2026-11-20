// Rôles métier d'une division (dictionnaire) et affectation manuelle des fichiers : créer, renommer,
// désactiver, supprimer un rôle ; affecter chaque fichier de la division à un ou plusieurs agents DE la
// division (le serveur contrôle le périmètre — 404 / 403 — et refuse un agent d'une autre division).
import { Search, UserSquare } from 'lucide-react'
import { Shield } from 'lucide-react'
import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../../shared/api/client'
import Badge from '../../shared/ui/Badge'
import { EmptyState, Loading } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import { useDebounce } from '../../shared/hooks/useDebounce'
import { useToast } from '../../shared/hooks/useToast'
import ErreurAcces from '../demandes/ErreurAcces'
import AffectationModal from '../documents/components/AffectationModal'
import { listDocuments } from '../documents/api'
import { useFiltres } from '../documents/queries'
import type { DocumentFilters, DocumentMeta } from '../documents/types'
import { useAuth } from '../auth/session'
import { creerRole, listDivisions, listRoles, modifierRole, supprimerRole } from './api'
import type { RoleDivision } from './api'

function Ligne({ r, onDone }: { r: RoleDivision; onDone: () => void }) {
  const toast = useToast()
  const [libelle, setLibelle] = useState(r.libelle)
  const run = (p: Promise<unknown>, ok: string) => p.then(() => { toast.success(ok); onDone() }).catch((e) => toast.error(errorMessage(e)))
  return (
    <tr>
      <td className="td"><input className="input" aria-label={`Libellé du rôle ${r.code}`} value={libelle} onChange={(e) => setLibelle(e.target.value)} /></td>
      <td className="td text-slate-600">{r.code}</td>
      <td className="td text-right">{r.nb_agents} agent(s)</td>
      <td className="td">{r.actif ? <Badge tone="green">Actif</Badge> : <Badge tone="gray">Inactif</Badge>}</td>
      <td className="td"><div className="flex justify-end gap-1">
        {libelle.trim() !== r.libelle && <button className="btn" onClick={() => void run(modifierRole(r.division_id, r.id, { libelle: libelle.trim() }), 'Rôle renommé.')}>Enregistrer</button>}
        <button className="btn-ghost" onClick={() => void run(modifierRole(r.division_id, r.id, { actif: !r.actif }), r.actif ? 'Rôle désactivé.' : 'Rôle réactivé.')}>{r.actif ? 'Désactiver' : 'Réactiver'}</button>
        <button className="btn-danger" onClick={() => { if (window.confirm(`Supprimer le rôle « ${r.libelle} » ?`)) void run(supprimerRole(r.division_id, r.id), 'Rôle supprimé.') }}>Supprimer</button>
      </div></td>
    </tr>
  )
}

/** Une ligne de fichier : affectations actuelles + bouton d'affectation (le serveur autorise le gérant seulement). */
function LigneFichier({ doc, onAffecter }: { doc: DocumentMeta; onAffecter: () => void }) {
  const mayAffect = doc.droits.includes('affecter') && !doc.corbeille_le
  return (
    <tr>
      <td className="td"><span className="font-medium text-black">{doc.titre}</span><p className="text-xs text-slate-600">{doc.cree_par_nom ? `déposé par ${doc.cree_par_nom}` : ''}</p></td>
      <td className="td">
        <div className="flex flex-wrap items-center gap-1">
          {doc.affectations.length === 0 ? <Badge tone="amber">À affecter</Badge>
            : doc.affectations.slice(0, 3).map((a) => <Badge key={a.id} tone="green">{a.prenom} {a.nom}</Badge>)}
          {doc.affectations.length > 3 && <span className="text-xs text-slate-600">+{doc.affectations.length - 3}</span>}
        </div>
      </td>
      <td className="td text-right">
        {mayAffect && <button className="btn-ghost" onClick={onAffecter}><UserSquare className="h-4 w-4" /> Affecter</button>}
      </td>
    </tr>
  )
}

export function Component() {
  const { user } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  // le super administrateur choisit parmi toutes les divisions ; le chef de service parmi celles de SON
  // service (le serveur renvoie déjà la liste scopée) ; le chef de division voit la sienne, fixe.
  const peutChoisir = user?.niveau === 'ROOT' || user?.niveau === 'SERVICE'
  const divisions = useQuery({ queryKey: ['divisions'], queryFn: listDivisions, enabled: peutChoisir })
  const [choix, setChoix] = useState<number | null>(null)
  const [libelle, setLibelle] = useState('')
  const divisionId = choix ?? user?.division_id ?? divisions.data?.[0]?.id ?? null
  const roles = useQuery({ queryKey: ['roles-division', divisionId], queryFn: () => listRoles(divisionId!), enabled: divisionId !== null })
  const refresh = () => qc.invalidateQueries({ queryKey: ['roles-division', divisionId] })
  const add = useMutation({ mutationFn: () => creerRole(divisionId!, { libelle: libelle.trim() }), onSuccess: () => { setLibelle(''); return refresh() } })
  // fichiers de la division choisie : le serveur ne renvoie que le périmètre du compte (chef de division :
  // sa division ; chef de service : ses divisions, filtrées ici par division ; super administrateur : rien —
  // il n'accède pas au contenu, sauf l'intérim d'une division vacante).
  // recherche et filtres de la liste des fichiers : appliqués par le serveur (q, a_affecter, agent_id, tri)
  const [recherche, setRecherche] = useState('')
  const q = useDebounce(recherche.trim())
  const [aAffecter, setAAffecter] = useState(false)
  const [agentId, setAgentId] = useState('')
  const [tri, setTri] = useState<NonNullable<DocumentFilters['tri']>>('titre_asc')
  const filtres = useFiltres()
  const agentsDivision = (filtres.data?.agents ?? []).filter((a) => a.division_id === divisionId)
  const filtresActifs = recherche !== '' || aAffecter || agentId !== ''
  const effacerFiltres = () => { setRecherche(''); setAAffecter(false); setAgentId('') }
  const params: DocumentFilters = {
    division_id: divisionId ?? undefined,
    q: q || undefined,
    a_affecter: aAffecter || undefined,
    agent_id: agentId ? Number(agentId) : undefined,
    tri,
    page: 1,
    taille: 100,
  }
  const fichiers = useQuery({
    queryKey: ['documents', 'list', params],
    queryFn: () => listDocuments(params),
    enabled: divisionId !== null,
    placeholderData: keepPreviousData, // la liste reste affichée pendant la frappe, sans clignotement
  })
  const [affectDoc, setAffectDoc] = useState<DocumentMeta | null>(null)

  if (divisionId === null) {
    // divisions du service pas encore chargées : attendre avant de conclure à « aucune division »
    if (divisions.isLoading || divisions.isError) return divisions.isError ? <ErreurAcces error={divisions.error} /> : <Loading />
    return <EmptyState icon={<Shield className="h-8 w-8" />} title="Aucune division à gérer" />
  }
  const items = fichiers.data?.items ?? []
  const total = fichiers.data?.total ?? items.length
  return (
    <div className="space-y-6">
      <PageHeader title="Rôles et affectation" description="Le dictionnaire de rôles décrit les agents de la division ; l'accès aux fichiers se décide par l'affectation manuelle : le chef affecte chaque fichier de la division à un ou plusieurs agents de la division — y compris les fichiers déposés par les agents."
        actions={peutChoisir && divisions.data ? (
          <select className="input w-64" aria-label="Division" value={divisionId} onChange={(e) => { setChoix(Number(e.target.value)); setAgentId('') }}>
            {divisions.data.map((d) => <option key={d.id} value={d.id}>{d.nom}{d.service_nom ? ` (${d.service_nom})` : ''}</option>)}
          </select>
        ) : null} />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-navy-700">Dictionnaire de rôles</h2>
        <div className="flex gap-2">
          <input className="input w-72" placeholder="Nouveau rôle (ex. Paie)" aria-label="Libellé du nouveau rôle" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          <button className="btn" disabled={libelle.trim().length < 2 || add.isPending}
            onClick={() => add.mutateAsync().then(() => toast.success('Rôle créé.')).catch((e) => toast.error(errorMessage(e)))}>Créer</button>
        </div>
        {roles.isLoading ? <Loading /> : roles.error ? <ErreurAcces error={roles.error} /> : (
          <div className="card overflow-x-auto"><table className="w-full text-left text-sm">
            <thead><tr><th className="th">Libellé</th><th className="th">Code</th><th className="th text-right">Utilisation</th><th className="th">État</th><th className="th" /></tr></thead>
            <tbody className="divide-y divide-slate-200">{(roles.data ?? []).map((r) => <Ligne key={`${r.id}-${r.libelle}-${r.actif}`} r={r} onDone={() => void refresh()} />)}</tbody>
          </table></div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-navy-700">Affectation des fichiers de la division</h2>
        <p className="text-sm text-slate-600">Un fichier affecté à un agent est lu par lui ; sans affectation, l'accès se demande. Les agents d'une autre division sont refusés par le serveur.</p>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-52 flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-600" aria-hidden />
            <input className="input pl-9" type="search" placeholder="Rechercher par titre ou nom de fichier…" aria-label="Rechercher un fichier de la division"
              value={recherche} onChange={(e) => setRecherche(e.target.value)} />
          </div>
          <select className="input w-auto" aria-label="Filtrer par affectation" value={aAffecter ? 'a_affecter' : ''} onChange={(e) => setAAffecter(e.target.value === 'a_affecter')}>
            <option value="">Tous les fichiers</option>
            <option value="a_affecter">À affecter</option>
          </select>
          <select className="input w-auto" aria-label="Filtrer par agent affecté" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
            <option value="">Tous les agents</option>
            {agentsDivision.map((a) => <option key={a.id} value={a.id}>{a.prenom} {a.nom}</option>)}
          </select>
          <select className="input w-auto" aria-label="Tri" value={tri} onChange={(e) => setTri(e.target.value as NonNullable<DocumentFilters['tri']>)}>
            <option value="titre_asc">Titre A → Z</option><option value="titre_desc">Titre Z → A</option><option value="date_desc">Plus récents</option>
          </select>
          {filtresActifs && <button className="btn-ghost" onClick={effacerFiltres}>Effacer les filtres</button>}
        </div>
        {fichiers.data && items.length > 0 && (
          <p className="text-sm text-slate-600" aria-live="polite">
            {total} fichier(s){filtresActifs ? ' correspondant(s)' : ''}{total > items.length ? ` — les ${items.length} premiers sont affichés, affinez la recherche pour voir les autres.` : ''}
          </p>
        )}
        {fichiers.isPending ? <Loading /> : fichiers.error ? <ErreurAcces error={fichiers.error} /> : items.length === 0 ? (
          filtresActifs
            ? <EmptyState icon={<Search className="h-8 w-8" />} title="Aucun fichier ne correspond à ces critères" action={<button className="btn-ghost" onClick={effacerFiltres}>Effacer les filtres</button>} />
            : <EmptyState icon={<UserSquare className="h-8 w-8" />} title="Aucun fichier dans cette division" />
        ) : (
          <div className={`card overflow-x-auto transition-opacity ${fichiers.isPlaceholderData ? 'pointer-events-none opacity-60' : ''}`}><table className="w-full text-left text-sm">
            <thead><tr><th className="th">Fichier</th><th className="th">Affectations</th><th className="th text-right" /></tr></thead>
            <tbody className="divide-y divide-slate-200">
              {items.map((d) => <LigneFichier key={d.id} doc={d} onAffecter={() => setAffectDoc(d)} />)}
            </tbody>
          </table></div>
        )}
      </section>

      {affectDoc && <AffectationModal doc={affectDoc} onClose={() => setAffectDoc(null)} />}
    </div>
  )
}
