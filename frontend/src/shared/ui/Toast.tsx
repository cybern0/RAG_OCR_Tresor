// Notifications éphémères (succès / erreur), affichées en bas à droite.
import { CheckCircle2, XCircle } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ToastContext } from '../hooks/useToast'
import type { ToastApi } from '../hooks/useToast'

interface ToastItem { id: number; kind: 'success' | 'error'; text: string }
let counter = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const push = useCallback((kind: ToastItem['kind'], text: string) => {
    const id = ++counter
    setItems((all) => [...all, { id, kind, text }])
    setTimeout(() => setItems((all) => all.filter((t) => t.id !== id)), kind === 'error' ? 7000 : 3500)
  }, [])

  const api = useMemo<ToastApi>(() => ({ success: (t) => push('success', t), error: (t) => push('error', t) }), [push])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-full max-w-sm flex-col gap-2" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} role={t.kind === 'error' ? 'alert' : 'status'}
            className={`pointer-events-auto flex animate-pop items-start gap-2 rounded-lg border px-3 py-2.5 text-sm shadow-xl ${t.kind === 'error' ? 'border-red-300 bg-red-50 text-red-800' : 'border-emerald-300 bg-white text-emerald-800'}`}>
            {t.kind === 'error' ? <XCircle className="mt-0.5 h-4 w-4 shrink-0" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
