// Racine de l'interface : connexion, puis navigation entre Dossiers et fichiers, Chatbot et Administration
// selon les permissions du compte.
import { useState } from 'react'
import { Loading } from './components/ui/Feedback'
import AdminPage from './features/admin/AdminPage'
import LoginPage from './features/auth/LoginPage'
import Chatbot from './features/chat/Chatbot'
import DashboardDocuments from './features/documents/DashboardDocuments'
import { useAuth } from './hooks/useAuth'

type Page = 'documents' | 'chat' | 'admin'

export default function App() {
  const { status, user, can, logout } = useAuth()
  const [requested, setRequested] = useState<Page | null>(null)

  if (status === 'loading') return <div className="flex min-h-svh items-center justify-center"><Loading /></div>
  if (status === 'anonymous' || !user) return <LoginPage />

  const pages: { id: Page; label: string; allowed: boolean }[] = [
    { id: 'documents', label: 'Dossiers et fichiers', allowed: can('document.lister') },
    { id: 'chat', label: 'Chatbot', allowed: can('chat.utiliser') },
    { id: 'admin', label: 'Administration', allowed: can('dossier.gerer') || can('utilisateur.lister') || can('structure.gerer') || can('audit.consulter') || can('statistiques.globales') || can('classement.gerer') },
  ]
  const visible = pages.filter((p) => p.allowed)
  const page = visible.find((p) => p.id === requested)?.id ?? visible[0]?.id

  return (
    <div className="min-h-svh">
      <header className="border-b border-gold-500/40 bg-leaf-950">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="flex items-center gap-2 text-lg font-bold text-gold-400">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gold-500 text-leaf-950">❦</span>
              Trésor RAG
            </span>
            <nav className="flex gap-1" aria-label="Navigation principale">
              {visible.map((p) => (
                <button key={p.id} onClick={() => setRequested(p.id)} aria-current={page === p.id ? 'page' : undefined}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${page === p.id ? 'bg-gold-500 text-leaf-950' : 'text-cream-100 hover:bg-gold-500/15'}`}>
                  {p.label}
                </button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-cream-300">
              <span className="font-medium text-cream-50">{user.nom_utilisateur}</span>
              {' · '}{user.role === 'ADMIN' ? 'Administrateur' : user.service_nom ?? 'Utilisateur'}
            </span>
            <button className="btn-ghost" onClick={() => void logout()}>Déconnexion</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl p-4">
        {!page && <p className="card p-8 text-center text-cream-300">Votre compte n'a accès à aucune fonctionnalité.</p>}
        {page === 'documents' && <DashboardDocuments />}
        {page === 'chat' && <Chatbot />}
        {page === 'admin' && <AdminPage />}
      </main>
    </div>
  )
}
