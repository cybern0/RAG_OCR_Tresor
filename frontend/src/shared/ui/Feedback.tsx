// États partagés : erreur, chargement, état vide, squelette.
import { AlertCircle, Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export function ErrorBox({ message, className }: { message: string | null | undefined; className?: string }) {
  if (!message) return null
  return (
    <p role="alert" className={cn('flex items-start gap-2 rounded-lg border border-red-300/60 bg-red-950/40 px-3 py-2 text-sm text-red-100', className)}>
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span>{message}</span>
    </p>
  )
}

export function Loading({ label = 'Chargement…', className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cn('flex items-center justify-center gap-2 py-10 text-sm text-cream-300', className)}>
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-leaf-700/50', className)} aria-hidden />
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-2 px-6 py-12 text-center">
      {icon && <div className="mb-1 text-gold-400">{icon}</div>}
      <p className="font-semibold text-cream-50">{title}</p>
      {children && <p className="max-w-md text-sm text-cream-300">{children}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

/** Charge une requête : squelette, erreur, ou contenu. */
export function QueryState({ isPending, error, children }: { isPending: boolean; error: string | null; children: ReactNode }) {
  if (error) return <ErrorBox message={error} />
  if (isPending) return <Loading />
  return <>{children}</>
}
