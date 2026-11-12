// Petits éléments d'état partagés : erreur, chargement.

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="rounded-lg border border-red-300/60 bg-red-950/40 px-3 py-2 text-sm text-red-100">
      {message}
    </p>
  )
}

export function Loading({ label = 'Chargement…' }: { label?: string }) {
  return <p className="py-8 text-center text-sm text-cream-300">{label}</p>
}
