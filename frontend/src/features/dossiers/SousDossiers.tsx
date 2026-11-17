// Sous-dossiers d'un dossier (liste + création). Les droits viennent du serveur (peut_creer).
import { FolderOpen, FolderPlus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../../shared/api/client'
import { useToast } from '../../shared/hooks/useToast'
import { createDossier } from './api'
import type { DossierDetail } from './types'

export default function SousDossiers({ d }: { d: DossierDetail }) {
  const toast = useToast()
  const qc = useQueryClient()
  const [nom, setNom] = useState('')
  const add = useMutation({
    mutationFn: () => createDossier({ nom: nom.trim(), parent_id: d.id }),
    onSuccess: () => { setNom(''); return qc.invalidateQueries({ queryKey: ['dossiers'] }) },
  })
  const sousDossiers = d.sous_dossiers ?? [] // champ absent si le backend déployé est d'une autre version
  if (sousDossiers.length === 0 && !d.peut_creer) return null
  return (
    <section className="mb-4 space-y-2">
      <div className="flex flex-wrap gap-2">
        {sousDossiers.map((s) => (
          <Link key={s.id} to={`/dossiers/${s.id}`} className="card flex items-center gap-2 px-3 py-2 text-sm hover:border-gold-400">
            <FolderOpen className="h-4 w-4 text-gold-400" aria-hidden /> {s.nom} <span className="text-xs text-cream-300">({s.nb_fichiers})</span>
          </Link>
        ))}
      </div>
      {d.peut_creer && !d.archive && (
        <div className="flex gap-2">
          <input className="input w-56" placeholder="Nouveau sous-dossier" aria-label="Nom du sous-dossier" value={nom} onChange={(e) => setNom(e.target.value)} />
          <button className="btn" disabled={!nom.trim() || add.isPending}
            onClick={() => add.mutateAsync().then(() => toast.success('Sous-dossier créé.')).catch((e) => toast.error(errorMessage(e)))}>
            <FolderPlus className="h-4 w-4" /> Créer
          </button>
        </div>
      )}
    </section>
  )
}
