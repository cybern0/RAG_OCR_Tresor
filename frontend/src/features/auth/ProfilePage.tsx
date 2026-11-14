// Mon profil (tout compte, administrateur compris) : nom d'utilisateur, et mot de passe avec vérification de l'ancien
// et confirmation du nouveau. Le rôle, le service et l'agent ne se modifient pas ici : c'est le rôle d'un administrateur.
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../shared/api/client'
import { useToast } from '../../shared/hooks/useToast'
import { exempleIdentifiant, exempleMotDePasse } from '../../shared/lib/exemples'
import { formatDate } from '../../shared/lib/format'
import Badge from '../../shared/ui/Badge'
import ExampleButton from '../../shared/ui/ExampleButton'
import Field from '../../shared/ui/Field'
import { ErrorBox } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import { saveProfile, useAuth } from './session'

const MIN = 10

function IdentityForm({ username }: { username: string }) {
  const toast = useToast()
  const [value, setValue] = useState(username)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const unchanged = value.trim().toLowerCase() === username

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try { await saveProfile({ nom_utilisateur: value }); toast.success('Nom d’utilisateur modifié.') } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="card space-y-4 p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold text-gold-400">Nom d’utilisateur</h2>
        <ExampleButton onFill={() => setValue(exempleIdentifiant())} />
      </div>
      <Field label="Nom d’utilisateur" hint="Minuscules, chiffres, point, tiret (3 à 80 caractères). C’est l’identifiant de connexion.">
        {(id) => <input id={id} className="input" required autoComplete="username" value={value} onChange={(e) => setValue(e.target.value)} />}
      </Field>
      <ErrorBox message={error} />
      <div className="flex justify-end"><button className="btn" disabled={busy || unchanged}>{busy ? 'Enregistrement…' : 'Enregistrer'}</button></div>
    </form>
  )
}

function PasswordForm() {
  const toast = useToast()
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const tooShort = newPwd.length > 0 && newPwd.length < MIN
  const mismatch = confirm.length > 0 && confirm !== newPwd
  const ready = oldPwd !== '' && newPwd.length >= MIN && confirm === newPwd

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!ready) return
    setBusy(true)
    setError(null)
    try {
      await saveProfile({ ancien_mot_de_passe: oldPwd, nouveau_mot_de_passe: newPwd, confirmation_mot_de_passe: confirm })
      setOldPwd(''); setNewPwd(''); setConfirm('')
      toast.success('Mot de passe modifié.')
    } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="card space-y-4 p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold text-gold-400">Mot de passe</h2>
        <ExampleButton onFill={() => { const p = exempleMotDePasse(); setNewPwd(p); setConfirm(p) }} />
      </div>
      <Field label="Mot de passe actuel">
        {(id) => <input id={id} type="password" className="input" autoComplete="current-password" required value={oldPwd} onChange={(e) => setOldPwd(e.target.value)} />}
      </Field>
      <Field label="Nouveau mot de passe" hint={tooShort ? undefined : `${MIN} caractères minimum.`}>
        {(id) => <input id={id} type="password" className="input" autoComplete="new-password" required minLength={MIN} aria-invalid={tooShort} value={newPwd} onChange={(e) => setNewPwd(e.target.value)} />}
      </Field>
      {tooShort && <p className="-mt-2 text-xs text-red-200">Encore {MIN - newPwd.length} caractère(s).</p>}
      <Field label="Confirmer le nouveau mot de passe">
        {(id) => <input id={id} type="password" className="input" autoComplete="new-password" required aria-invalid={mismatch} value={confirm} onChange={(e) => setConfirm(e.target.value)} />}
      </Field>
      {mismatch && <p className="-mt-2 text-xs text-red-200">La confirmation ne correspond pas.</p>}
      <ErrorBox message={error} />
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-cream-300">Vous restez connecté sur cet appareil ; les autres sessions ouvertes seront fermées.</p>
        <button className="btn shrink-0" disabled={busy || !ready}>{busy ? 'Enregistrement…' : 'Changer le mot de passe'}</button>
      </div>
    </form>
  )
}

export function Component() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <>
      <PageHeader title="Mon profil" description="Vos informations de connexion." />
      <div className="grid max-w-5xl gap-5 lg:grid-cols-2">
        <div className="space-y-5">
          <section className="card p-5">
            <h2 className="mb-3 font-semibold text-gold-400">Compte</h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-3"><dt className="text-cream-300">Rôle</dt><dd><Badge tone={user.role === 'ADMIN' ? 'gold' : 'gray'}>{user.role === 'ADMIN' ? 'Administrateur' : 'Utilisateur'}</Badge></dd></div>
              {user.agent && <div className="flex justify-between gap-3"><dt className="text-cream-300">Agent</dt><dd>{user.agent.nom} {user.agent.prenom}</dd></div>}
              {user.service_nom && <div className="flex justify-between gap-3"><dt className="text-cream-300">Service</dt><dd>{user.service_nom}</dd></div>}
              <div className="flex justify-between gap-3"><dt className="text-cream-300">Dernière connexion</dt><dd>{formatDate(user.derniere_connexion)}</dd></div>
            </dl>
            <p className="mt-3 text-xs text-cream-300">Le rôle, l’agent et le service sont gérés par un administrateur.</p>
          </section>
          <IdentityForm key={user.nom_utilisateur} username={user.nom_utilisateur} />
        </div>
        <PasswordForm />
      </div>
    </>
  )
}
