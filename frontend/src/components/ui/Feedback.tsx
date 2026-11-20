// Petits éléments d'état partagés : erreur, chargement.

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
      {message}
    </p>
  )
}

export function Loading({ label = 'Chargement…' }: { label?: string }) {
  return <p className="py-8 text-center text-sm text-slate-600">{label}</p>
}
