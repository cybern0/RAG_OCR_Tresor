import { useId } from 'react'
import type { ReactNode } from 'react'

/** Champ de formulaire : étiquette liée, aide et contrôle ; le contrôle reçoit son identifiant par fonction. */
export default function Field({ label, hint, children, className }: { label: string; hint?: ReactNode; children: (id: string) => ReactNode; className?: string }) {
  const id = useId()
  return (
    <div className={className}>
      <label className="label" htmlFor={id}>{label}</label>
      {children(id)}
      {hint && <p className="mt-1 text-xs text-slate-600">{hint}</p>}
    </div>
  )
}
