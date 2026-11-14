import { Link, isRouteErrorResponse, useRouteError } from 'react-router'

export function ErrorPage() {
  const error = useRouteError()
  const message = isRouteErrorResponse(error) ? `${error.status} — ${error.statusText}` : error instanceof Error ? error.message : 'Erreur inattendue.'
  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <div className="card max-w-md space-y-3 p-8 text-center">
        <h1 className="text-xl font-bold text-gold-400">Une erreur est survenue</h1>
        <p className="text-sm text-cream-300">{message}</p>
        <div className="flex justify-center gap-2 pt-2">
          <button className="btn-ghost" onClick={() => window.location.reload()}>Recharger</button>
          <Link className="btn" to="/">Accueil</Link>
        </div>
      </div>
    </main>
  )
}

export function Component() {
  return (
    <div className="card mx-auto max-w-md space-y-3 p-10 text-center">
      <p className="text-5xl font-bold text-gold-400">404</p>
      <p className="text-cream-300">Cette page n’existe pas ou a été déplacée.</p>
      <Link className="btn" to="/">Retour à l’accueil</Link>
    </div>
  )
}
