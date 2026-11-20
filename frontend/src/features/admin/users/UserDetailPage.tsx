// Page d'un compte (administration) : rôle, agent, activation, et réinitialisation du mot de passe en un clic, sans
// vérification de l'ancien. Pour son propre compte, l'administrateur passe par « Mon profil » (ancien mot de passe exigé).
import { ArrowLeft, Copy, Dices, KeyRound } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { errorMessage } from '../../../shared/api/client'
import { useToast } from '../../../shared/hooks/useToast'
import { exempleMotDePasse } from '../../../shared/lib/exemples'
import { formatDate } from '../../../shared/lib/format'
import Badge from '../../../shared/ui/Badge'
import ExampleButton from '../../../shared/ui/ExampleButton'
import Field from '../../../shared/ui/Field'
import { ErrorBox, Loading } from '../../../shared/ui/Feedback'
import PageHeader from '../../../shared/ui/PageHeader'
import { useAuth } from '../../auth/session'
import type { Role, UserOut } from '../../auth/types'
import RolesAgentPanel from '../../roles/RolesAgentPanel'
import { updateUser } from '../api'
import { adminKeys, useAdminMutation, useAgentsDisponibles, useUser } from '../queries'

const ALPHABET = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'

/** Mot de passe aléatoire (sans caractères ambigus), tiré avec le générateur cryptographique du navigateur. */
function generatePassword(length = 14): string {
  const limit = 256 - (256 % ALPHABET.length) // évite le biais du modulo
  let out = ''
  while (out.length < length) {
    for (const byte of crypto.getRandomValues(new Uint8Array(length))) {
      if (byte < limit && out.length < length) out += ALPHABET[byte % ALPHABET.length]
    }
  }
  return out
}

function AccountForm({ target, canEdit, canChangeRole, isSelf }: { target: UserOut; canEdit: boolean; canChangeRole: boolean; isSelf: boolean }) {
  const toast = useToast()
  const agents = useAgentsDisponibles(target.id)
  const [role, setRole] = useState<Role>(target.role)
  const [agentId, setAgentId] = useState<number | ''>(target.agent?.id ?? '')
  const [actif, setActif] = useState(target.actif)
  const [error, setError] = useState<string | null>(null)
  const save = useAdminMutation(() => updateUser(target.id, {
    role: role !== target.role ? role : undefined,
    agent_id: agentId && agentId !== target.agent?.id ? agentId : undefined,
    retirer_agent: !agentId && target.agent !== null ? true : undefined,
    actif: actif !== target.actif ? actif : undefined,
  }), [adminKeys.users, adminKeys.agents])
  const free = agents.data ?? []
  const changed = role !== target.role || (agentId || null) !== (target.agent?.id ?? null) || actif !== target.actif

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try { await save.mutateAsync(undefined); toast.success('Compte modifié.') } catch (err) { setError(errorMessage(err)) }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="card space-y-4 p-5">
      <h2 className="font-semibold text-navy-700">Compte</h2>
      <Field label="Rôle">
        {(id) => (
          <select id={id} className="input" disabled={!canChangeRole || isSelf} value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="UTILISATEUR">Utilisateur (accès par rôles)</option>
            {canChangeRole && <option value="ADMIN">Administrateur (tout)</option>}
          </select>
        )}
      </Field>
      <Field label={`Agent${role === 'UTILISATEUR' ? '' : ' (facultatif)'}`} hint="Son service et sa division en découlent : ils déterminent les fichiers accessibles.">
        {(id) => (
          <select id={id} className="input" disabled={!canEdit || (isSelf && !canChangeRole)} required={role === 'UTILISATEUR'} value={agentId} onChange={(e) => setAgentId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">— Aucun —</option>
            {free.map((a) => <option key={a.id} value={a.id}>{a.nom} {a.prenom} — {a.service_nom}</option>)}
          </select>
        )}
      </Field>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4 accent-navy-700" disabled={!canEdit || isSelf} checked={actif} onChange={(e) => setActif(e.target.checked)} /> Compte actif
      </label>
      {isSelf && <p className="text-xs text-slate-600">Vous ne pouvez pas modifier votre propre rôle ni désactiver votre propre compte.</p>}
      <ErrorBox message={error} />
      {canEdit && <div className="flex justify-end"><button className="btn" disabled={save.isPending || !changed}>{save.isPending ? 'Enregistrement…' : 'Enregistrer'}</button></div>}
    </form>
  )
}

function PasswordReset({ target, isSelf }: { target: UserOut; isSelf: boolean }) {
  const toast = useToast()
  const [password, setPassword] = useState('')
  const [revealed, setRevealed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const reset = useAdminMutation((value: string) => updateUser(target.id, { mot_de_passe: value }), [adminKeys.users])

  if (isSelf) {
    return (
      <section className="card space-y-3 p-5">
        <h2 className="font-semibold text-navy-700">Mot de passe</h2>
        <p className="text-sm text-slate-600">Pour votre propre compte, le changement exige votre mot de passe actuel et une confirmation.</p>
        <Link className="btn-ghost w-fit" to="/profil"><KeyRound className="h-4 w-4" /> Changer mon mot de passe</Link>
      </section>
    )
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await reset.mutateAsync(password)
      toast.success(`Mot de passe de ${target.nom_utilisateur} modifié.`)
      setPassword('')
    } catch (err) { setError(errorMessage(err)) }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="card space-y-4 p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold text-navy-700">Mot de passe</h2>
        <ExampleButton onFill={() => { setPassword(exempleMotDePasse()); setRevealed(true) }} />
      </div>
      <p className="text-sm text-slate-600">Définit directement un nouveau mot de passe, sans demander l’ancien. Ses sessions ouvertes seront fermées ; communiquez-lui le nouveau mot de passe.</p>
      <Field label="Nouveau mot de passe" hint="10 caractères minimum.">
        {(id) => (
          <div className="flex gap-2">
            <input id={id} type={revealed ? 'text' : 'password'} className="input font-mono" autoComplete="new-password" required minLength={10} value={password}
              onChange={(e) => { setPassword(e.target.value); setRevealed(false) }} />
            <button type="button" className="btn-ghost shrink-0" onClick={() => { setPassword(generatePassword()); setRevealed(true) }}><Dices className="h-4 w-4" /> Générer</button>
            <button type="button" className="btn-icon shrink-0" disabled={!password} aria-label="Copier le mot de passe" title="Copier"
              onClick={() => void navigator.clipboard.writeText(password).then(() => toast.success('Mot de passe copié.')).catch(() => toast.error('Copie impossible.'))}><Copy className="h-4 w-4" /></button>
          </div>
        )}
      </Field>
      <ErrorBox message={error} />
      <div className="flex justify-end"><button className="btn" disabled={reset.isPending || password.length < 10}>{reset.isPending ? 'Enregistrement…' : 'Définir le mot de passe'}</button></div>
    </form>
  )
}

export function Component() {
  const id = Number(useParams().userId)
  const { can, user: me } = useAuth()
  const user = useUser(id)

  if (user.isPending) return <Loading />
  if (user.error || !user.data) return <ErrorBox message={user.error ? errorMessage(user.error) : 'Compte introuvable.'} />
  const u = user.data
  const isSelf = u.id === me?.id
  const canEdit = can('utilisateur.modifier')

  return (
    <>
      <PageHeader
        back={<Link to="/admin/utilisateurs" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-navy-600"><ArrowLeft className="h-4 w-4" /> Tous les utilisateurs</Link>}
        title={u.nom_utilisateur}
        description={<span className="flex flex-wrap items-center gap-2">{u.actif ? <Badge tone="green">Actif</Badge> : <Badge tone="red">Désactivé</Badge>}<Badge tone={u.role === 'ADMIN' ? 'gold' : 'gray'}>{u.role === 'ADMIN' ? 'Administrateur' : 'Utilisateur'}</Badge>{isSelf && <span>(vous)</span>} · dernière connexion : {formatDate(u.derniere_connexion)}</span>} />
      <div className="grid max-w-5xl gap-5 lg:grid-cols-2">
        <AccountForm key={`${u.role}-${u.agent?.id}-${u.actif}`} target={u} canEdit={canEdit} canChangeRole={canEdit && me?.niveau === 'ROOT'} isSelf={isSelf} />
        {u.agent?.division_id ? <RolesAgentPanel userId={u.id} divisionId={u.agent.division_id} divisionNom={u.agent.division_nom ?? ''} /> : null}
        {canEdit ? <PasswordReset key={u.id} target={u} isSelf={isSelf} /> : null}
      </div>
    </>
  )
}
