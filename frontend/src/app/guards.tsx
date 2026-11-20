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

/** Historique : réservé aux niveaux d'administration (ROOT, SERVICE, DIVISION), comme le menu du même nom. */
export function RequireNiveauAdmin() {
  const { user } = useAuth()
  if (!user || user.niveau === 'AGENT') return <Navigate to="/" replace />
  return <Outlet />
}

/** Réservé au super administrateur (gestion des agents et de la structure). */
export function RequireRoot() {
  const { user } = useAuth()
  if (!user || user.niveau !== 'ROOT') return <Navigate to="/" replace />
  return <Outlet />
}

/** Réservé aux comptes dont le niveau hiérarchique est listé (ex. chef de service, chef de division). */
export function RequireNiveau({ niveaux }: { niveaux: string[] }) {
  const { user } = useAuth()
  if (!user || !niveaux.includes(user.niveau)) return <Navigate to="/" replace />
  return <Outlet />
}

/** Page d'accueil : première page accessible au compte. */
export function Home() {
  const { user, can } = useAuth()
  const target = homePath(can, user?.niveau)
  if (!target) return <p className="card p-8 text-center text-slate-600">Votre compte n’a accès à aucune fonctionnalité.</p>
  return <Navigate to={target} replace />
}
