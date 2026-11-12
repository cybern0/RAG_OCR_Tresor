// Petit hook de chargement : appelle `fetcher` au montage (et quand il change), expose données, erreur et rechargement.
// `fetcher` doit être stable (useCallback) si elle dépend de valeurs.
import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage } from '../api/client'

export function useLoad<T>(fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const sequence = useRef(0)

  const reload = useCallback(async () => {
    const current = ++sequence.current
    try {
      const result = await fetcher()
      if (current !== sequence.current) return // une requête plus récente a pris le relais
      setData(result)
      setError(null)
    } catch (e) {
      if (current === sequence.current) setError(errorMessage(e))
    } finally {
      if (current === sequence.current) setLoading(false)
    }
  }, [fetcher])

  // Chargement initial (et à chaque changement de `fetcher`) ; les mises à jour d'état se font dans les callbacks.
  useEffect(() => {
    let cancelled = false
    const current = ++sequence.current
    fetcher()
      .then((result) => {
        if (cancelled || current !== sequence.current) return
        setData(result)
        setError(null)
        setLoading(false)
      })
      .catch((e: unknown) => {
        if (cancelled || current !== sequence.current) return
        setError(errorMessage(e))
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [fetcher])

  return { data, error, loading, reload }
}
