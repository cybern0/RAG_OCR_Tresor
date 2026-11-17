// Types de la structure (directions, services, agents) et du journal d'audit.

export interface Direction {
  id: number
  code: string
  nom: string
  actif: boolean
}

export interface ServiceItem {
  id: number
  code: string
  nom: string
  site: string | null
  actif: boolean
  direction_id: number
  direction_nom: string
}

export interface Agent {
  id: number
  matricule: string
  nom: string
  prenom: string
  fonction: string | null
  email: string | null
  service_id: number | null
  service_nom: string | null
  division_id: number | null
  division_nom: string | null
  titre: 'CHEF_DIVISION' | null
  actif: boolean
  nom_utilisateur: string | null
}

export interface AuditRow {
  id: number
  cree_le: string
  nom_utilisateur: string | null
  action: string
  entite: string | null
  entite_id: number | null
  detail: Record<string, unknown>
  adresse_ip: string | null
}
