// Bouton « Remplir avec exemple » : présent au-dessus de chaque formulaire, il remplit les champs avec de fausses
// informations (ils restent vides tant qu'on ne clique pas). Utile pour la démonstration et les essais.
import { Wand2 } from 'lucide-react'
import { cn } from '../lib/cn'

export default function ExampleButton({ onFill, className }: { onFill: () => void; className?: string }) {
  return (
    <button type="button" onClick={onFill}
      className={cn('inline-flex items-center gap-1.5 text-xs font-medium text-navy-700 underline decoration-dotted underline-offset-4 hover:text-navy-600', className)}>
      <Wand2 className="h-3.5 w-3.5" aria-hidden /> Remplir avec exemple
    </button>
  )
}
