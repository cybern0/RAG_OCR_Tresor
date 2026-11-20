import { LOGO_SRC } from '../../app/brand'
import { cn } from '../lib/cn'

// Logo de l'application (image). Décoratif : le nom de l'application est toujours affiché à côté.
export default function Logo({ className }: { className?: string }) {
  return <img src={LOGO_SRC} alt="" aria-hidden draggable={false} className={cn('block object-contain', className)} />
}
