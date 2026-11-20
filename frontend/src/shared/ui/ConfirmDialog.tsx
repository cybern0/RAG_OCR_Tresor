import { useState } from 'react'
import type { ReactNode } from 'react'
import { errorMessage } from '../api/client'
import { ErrorBox } from './Feedback'
import Modal from './Modal'

interface Props {
  title: string
  children: ReactNode
  confirmLabel: string
  danger?: boolean
  onConfirm: () => Promise<unknown>
  onClose: () => void
}

/** Confirmation d'une action (souvent destructrice) : affiche l'erreur du serveur sans fermer la fenêtre. */
export default function ConfirmDialog({ title, children, confirmLabel, danger = true, onConfirm, onClose }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      await onConfirm()
      onClose()
    } catch (e) {
      setError(errorMessage(e))
      setBusy(false)
    }
  }

  return (
    <Modal title={title} onClose={onClose} size="sm">
      <div className="text-sm text-black">{children}</div>
      <ErrorBox message={error} className="mt-4" />
      <div className="mt-5 flex justify-end gap-2">
        <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
        <button type="button" className={danger ? 'btn-danger' : 'btn'} disabled={busy} onClick={() => void confirm()}>{busy ? 'Patienter…' : confirmLabel}</button>
      </div>
    </Modal>
  )
}
