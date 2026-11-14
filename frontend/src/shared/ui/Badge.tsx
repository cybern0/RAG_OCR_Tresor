import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

const TONES = {
  gold: 'border-gold-500/60 text-gold-300',
  green: 'border-emerald-300/60 bg-emerald-400/10 text-emerald-100',
  red: 'border-red-300/60 bg-red-400/10 text-red-100',
  gray: 'border-cream-300/40 text-cream-100',
  amber: 'border-amber-300/50 bg-amber-400/10 text-amber-100',
} as const

export default function Badge({ tone = 'gray', children, className }: { tone?: keyof typeof TONES; children: ReactNode; className?: string }) {
  return <span className={cn('badge', TONES[tone], className)}>{children}</span>
}
