// Types des dossiers, de leurs rôles et des accès (membres directs et services).

export type RoleDossier = 'LECTEUR' | 'CONTRIBUTEUR' | 'GESTIONNAIRE_DE_CONTENU'

export const ROLES_DOSSIER: { id: RoleDossier; label: string; aide: string }[] = [
  { id: 'LECTEUR', label: 'Lecteur', aide: 'Voit, aperçoit, télécharge et interroge' },
  { id: 'CONTRIBUTEUR', label: 'Contributeur', aide: 'Lecteur + ajoute des fichiers et des versions, modifie' },
  { id: 'GESTIONNAIRE_DE_CONTENU', label: 'Gestionnaire de contenu', aide: 'Contributeur + supprime fichiers et versions' },
]

export const roleLabel = (r: RoleDossier) => ROLES_DOSSIER.find((x) => x.id === r)?.label ?? r

/** Actions permises par rôle (miroir de la matrice du backend, qui reste la seule autorité). */
export const canAdd = (r: RoleDossier) => r === 'CONTRIBUTEUR' || r === 'GESTIONNAIRE_DE_CONTENU'
export const canDelete = (r: RoleDossier) => r === 'GESTIONNAIRE_DE_CONTENU'

export interface Dossier {
  id: number
  nom: string
  description: string | null
  archive: boolean
  nb_fichiers: number
  mon_role: RoleDossier
  cree_le: string
  modifie_le: string
}

export interface Membre {
  user_id: number
  nom_utilisateur: string
  nom_complet: string | null
  role: RoleDossier
}

export interface ServiceAcces {
  service_id: number
  service_code: string
  service_nom: string
  role: RoleDossier
}

export interface AccesDossier {
  membres: Membre[]
  services: ServiceAcces[]
}
