import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

const TONES = {
  gold: 'border-navy-600/40 bg-navy-50 text-navy-700',
  green: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  red: 'border-red-300 bg-red-50 text-red-800',
  gray: 'border-slate-300 bg-white text-slate-700',
  amber: 'border-amber-300 bg-amber-50 text-amber-800',
} as const

export default function Badge({ tone = 'gray', children, className }: { tone?: keyof typeof TONES; children: ReactNode; className?: string }) {
  return <span className={cn('badge', TONES[tone], className)}>{children}</span>
}
