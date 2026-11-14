import { Leaf } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router'
import { errorMessage } from '../../shared/api/client'
import { exempleIdentifiant, exempleMotDePasse } from '../../shared/lib/exemples'
import ExampleButton from '../../shared/ui/ExampleButton'
import Field from '../../shared/ui/Field'
import { ErrorBox } from '../../shared/ui/Feedback'
import { signIn, useAuth } from './session'

export function Component() {
  const { status } = useAuth()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (status === 'authenticated') return <Navigate to={from} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn(username, password)
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-svh items-center justify-center bg-gradient-to-br from-leaf-950 via-leaf-900 to-leaf-800 p-4">
      <form onSubmit={(e) => void submit(e)} className="card w-full max-w-sm animate-pop space-y-4 p-8">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-gold-500 text-leaf-950"><Leaf className="h-6 w-6" /></div>
          <h1 className="text-2xl font-bold text-gold-400">Trésor RAG</h1>
          <p className="mt-1 text-sm text-cream-300">Assistant documentaire de vos dossiers</p>
        </div>
        <div className="flex justify-end">
          <ExampleButton onFill={() => { setUsername(exempleIdentifiant()); setPassword(exempleMotDePasse()) }} />
        </div>
        <Field label="Nom d’utilisateur">
          {(id) => <input id={id} className="input" autoComplete="username" autoFocus required value={username} onChange={(e) => setUsername(e.target.value)} />}
        </Field>
        <Field label="Mot de passe">
          {(id) => <input id={id} type="password" className="input" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <ErrorBox message={error} />
        <button className="btn w-full" disabled={busy}>{busy ? 'Connexion…' : 'Se connecter'}</button>
      </form>
    </main>
  )
}
