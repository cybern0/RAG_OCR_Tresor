// Liste des dossiers accessibles : cartes avec rôle, nombre de fichiers et état.
import { Archive, FileText, FolderOpen, Search } from 'lucide-react'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { useAuth } from '../auth/session'
import ErreurAcces from '../demandes/ErreurAcces'
import { listDivisions } from '../roles/api'
import { plural } from '../../shared/lib/format'
import Badge from '../../shared/ui/Badge'
import { EmptyState, Skeleton } from '../../shared/ui/Feedback'
import PageHeader from '../../shared/ui/PageHeader'
import { useDossiers } from './queries'

export function Component() {
  const { user } = useAuth()
  const canChooseDivision = user?.niveau === 'ROOT'
  const divisions = useQuery({ queryKey: ['divisions'], queryFn: listDivisions, enabled: canChooseDivision })
  const [choix, setChoix] = useState<number | null>(user?.division_id ?? null)
  const divisionId = canChooseDivision ? (choix ?? divisions.data?.[0]?.id ?? null) : user?.division_id ?? null
  const dossiers = useDossiers(divisionId)
  const [search, setSearch] = useState('')
  // Le serveur doit renvoyer un tableau ; si une version déployée renvoie autre chose (objet, enveloppe), on ignore
  // au lieu de planter la page (`.filter is not a function`).
  const donnees = Array.isArray(dossiers.data) ? dossiers.data : []
  const list = donnees.filter((d) => d.parent_id === null).filter((d) => `${d.nom} ${d.description ?? ''}`.toLowerCase().includes(search.trim().toLowerCase()))

  return (
    <>
      <PageHeader title="Dossiers et fichiers" description="Les dossiers auxquels vous avez accès. Ouvrez-en un pour consulter, ajouter et versionner ses fichiers."
        actions={(
          <div className="flex items-center gap-2">
            {canChooseDivision && divisions.data && divisions.data.length > 0 && (
              <select className="input w-64" value={divisionId ?? ''} onChange={(e) => setChoix(e.target.value ? Number(e.target.value) : null)} aria-label="Division">
                <option value="">— Choisir une division —</option>
                {divisions.data.map((d) => <option key={d.id} value={d.id}>{d.nom}{d.service_nom ? ` (${d.service_nom})` : ''}</option>)}
              </select>
            )}
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-cream-300" aria-hidden />
              <input className="input w-64 pl-9" type="search" placeholder="Rechercher un dossier…" aria-label="Rechercher un dossier" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
          </div>
        )} />
      {divisionId === null ? (
        <EmptyState icon={<FolderOpen className="h-8 w-8" />} title="Aucune division sélectionnée">
          {canChooseDivision ? 'Sélectionnez une division pour afficher les dossiers.' : 'Votre compte n’est rattaché à aucune division pour le moment.'}
        </EmptyState>
      ) : (
        <>
          {dossiers.error ? (
            <ErreurAcces error={dossiers.error} />
          ) : dossiers.isPending ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-32" />)}</div>
          ) : list.length === 0 ? (
            <EmptyState icon={<FolderOpen className="h-8 w-8" />} title={search ? 'Aucun dossier ne correspond' : 'Aucun dossier disponible'}>
              {search ? 'Essayez un autre terme de recherche.' : 'Aucun dossier dans votre division pour le moment.'}
            </EmptyState>
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {list.map((d) => (
                <li key={d.id}>
                  <Link to={`/dossiers/${d.id}`} className="card group block h-full p-4 transition hover:border-gold-400 hover:bg-leaf-700/60">
                    <div className="flex items-start justify-between gap-2">
                      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-gold-500/15 text-gold-400">
                        {d.archive ? <Archive className="h-5 w-5" /> : <FolderOpen className="h-5 w-5" />}
                      </span>
                      <Badge tone="gold">{d.division_nom}</Badge>
                    </div>
                    <h2 className="mt-3 truncate font-semibold text-cream-50 group-hover:text-gold-300">{d.nom}</h2>
                    <p className="mt-0.5 line-clamp-2 min-h-10 text-sm text-cream-300">{d.description ?? 'Aucune description.'}</p>
                    <p className="mt-2 flex items-center gap-2 text-xs text-cream-300">
                      <FileText className="h-3.5 w-3.5" aria-hidden /> {plural(d.nb_fichiers, 'fichier')}
                      {d.nb_fichiers_masques > 0 && <span>· {d.nb_fichiers_masques} non accessible(s)</span>}
                      {d.archive && <Badge tone="amber">Archivé</Badge>}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </>
  )
}
