// Message d'erreur d'accès : 403 sur un fichier → formulaire « Demander l'accès » ; autre erreur → message simple.
// Le serveur décide ; l'interface ne fait que guider.
import { useState } from 'react'
import { ApiError, errorMessage } from '../../shared/api/client'
import { useToast } from '../../shared/hooks/useToast'
import { ErrorBox } from '../../shared/ui/Feedback'
import { creerDemande } from './api'

export default function ErreurAcces({ error, documentId }: { error: unknown; documentId?: number }) {
  const toast = useToast()
  const [motif, setMotif] = useState('')
  const [heures, setHeures] = useState(24)
  const [envoye, setEnvoye] = useState(false)
  if (error instanceof ApiError && error.status === 403 && documentId !== undefined) {
    return (
      <div className="card space-y-2 p-4">
        <p className="text-sm">{error.message}</p>
        {envoye ? <p className="text-sm text-emerald-200">Demande envoyée : vous serez notifié de la réponse.</p> : (
          <div className="flex flex-wrap gap-2">
            <input className="input w-72" placeholder="Motif de la demande" aria-label="Motif" value={motif} onChange={(e) => setMotif(e.target.value)} />
            <input className="input w-24" type="number" min={1} max={720} aria-label="Durée en heures" value={heures} onChange={(e) => setHeures(Number(e.target.value))} />
            <button className="btn" disabled={motif.trim().length < 3}
              onClick={() => creerDemande({ type_demande: 'fichier', cible_id: documentId, motif: motif.trim(), duree_heures: heures }).then(() => setEnvoye(true)).catch((e) => toast.error(errorMessage(e)))}>
              Demander l’accès
            </button>
          </div>
        )}
      </div>
    )
  }
  return <ErrorBox message={errorMessage(error)} />
}
