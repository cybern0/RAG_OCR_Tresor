// Affectation manuelle d'un fichier : cases à cocher parmi les agents actifs de SA division, enregistrées
// d'un coup (avec motif facultatif). Réservé au gérant de la division (chef de division ou chef de service) —
// même si le fichier vient d'un agent ; le serveur refuse un agent d'une autre division (422).
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import Field from '../../../shared/ui/Field'
import { ErrorBox, Loading } from '../../../shared/ui/Feedback'
import Modal from '../../../shared/ui/Modal'
import { useToast } from '../../../shared/hooks/useToast'
import { listAgentsDivision } from '../../roles/api'
import { useDocumentMutations } from '../queries'
import type { DocumentMeta } from '../types'

export default function AffectationModal({ doc, onClose }: { doc: DocumentMeta; onClose: () => void }) {
  const { affecter } = useDocumentMutations()
  const toast = useToast()
  const agents = useQuery({ queryKey: ['agents-division', doc.division_id], queryFn: () => listAgentsDivision(doc.division_id) })
  const [edit, setEdit] = useState<Set<number> | null>(null)
  const [motif, setMotif] = useState('')
  const [error, setError] = useState<string | null>(null)
  const base = new Set(doc.affectations.map((a) => a.id))
  const sel = edit ?? base
  const changed = sel.size !== base.size || [...sel].some((i) => !base.has(i))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await affecter.mutateAsync({ id: doc.id, agentIds: [...sel], motif: motif.trim() || undefined })
      toast.success(doc.affectations.length === 0 && sel.size > 0 ? 'Fichier affecté.' : 'Affectations enregistrées.')
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Modal title={`Affecter « ${doc.titre} »`} onClose={onClose}>
      {agents.isPending ? <Loading /> : (
        <form onSubmit={(e) => void submit(e)} className="space-y-4">
          <p className="text-xs text-slate-600">
            Agents de la division « {doc.division_nom} » — les agents cochés pourront lire ce fichier ; l'auteur et
            les chefs y accèdent de toute façon. Sans affectation, l'accès reste refusé par défaut.
          </p>
          {(agents.data ?? []).length === 0 ? <p className="text-sm text-slate-600">Aucun agent actif dans cette division.</p> : (
            <ul className="space-y-1">{(agents.data ?? []).map((a) => (
              <li key={a.id}><label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-4 w-4 accent-navy-700" checked={sel.has(a.id)}
                  onChange={(e) => { const n = new Set(sel); if (e.target.checked) n.add(a.id); else n.delete(a.id); setEdit(n) }} />
                {a.prenom} {a.nom} <span className="text-slate-600">· {a.matricule}</span>
              </label></li>
            ))}</ul>
          )}
          <Field label="Motif" hint="Facultatif, conservé dans l'historique.">
            {(id) => <input id={id} className="input" placeholder="Ex. Mission audit" value={motif} onChange={(e) => setMotif(e.target.value)} />}
          </Field>
          <ErrorBox message={error} />
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-ghost" onClick={onClose}>Annuler</button>
            <button className="btn" disabled={!changed || affecter.isPending}>{affecter.isPending ? 'Enregistrement…' : 'Enregistrer les affectations'}</button>
          </div>
        </form>
      )}
    </Modal>
  )
}
