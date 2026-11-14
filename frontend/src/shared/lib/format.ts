// Formats d'affichage (français).
export const formatSize = (bytes: number | null | undefined) =>
  bytes == null
    ? '—'
    : bytes < 1024 * 1024
      ? `${Math.max(1, Math.round(bytes / 1024))} Ko`
      : bytes < 1024 ** 3
        ? `${(bytes / 1024 / 1024).toFixed(1)} Mo`
        : `${(bytes / 1024 ** 3).toFixed(2)} Go`

export const formatDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : '—'

export const formatDay = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '—')

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n > 1 ? many : one}`
