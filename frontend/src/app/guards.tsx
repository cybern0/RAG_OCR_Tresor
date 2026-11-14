import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '../features/auth/session'
import { Loading } from '../shared/ui/Feedback'
import { homePath } from './nav'

/** Exige une session ; sinon renvoie à la connexion en mémorisant la page demandée. */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <div className="flex min-h-svh items-center justify-center"><Loading /></div>
  if (status === 'anonymous') return <Navigate to="/connexion" replace state={{ from: location.pathname + location.search }} />
  return <Outlet />
}

/** Exige l'une des permissions listées (l'API reste l'autorité : ceci évite seulement d'afficher une page vide). */
export function RequirePermission({ any }: { any: string[] }) {
  const { canAny } = useAuth()
  return canAny(...any) ? <Outlet /> : <Navigate to="/" replace />
}

/** Page d'accueil : première page accessible au compte. */
export function Home() {
  const { can } = useAuth()
  const target = homePath(can)
  if (!target) return <p className="card p-8 text-center text-cream-300">Votre compte n’a accès à aucune fonctionnalité.</p>
  return <Navigate to={target} replace />
}
