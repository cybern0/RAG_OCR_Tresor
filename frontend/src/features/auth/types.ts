// Types des utilisateurs, rôles et permissions.
export type Role = 'ADMIN' | 'UTILISATEUR'

export interface AgentBrief {
  id: number
  matricule: string
  nom: string
  prenom: string
  service_id: number | null
  service_nom: string | null
}

export interface UserOut {
  id: number
  nom_utilisateur: string
  role: Role
  actif: boolean
  derniere_connexion: string | null
  cree_le: string
  agent: AgentBrief | null
}

/** Utilisateur connecté, avec ses permissions et son service. */
export interface Me extends UserOut {
  permissions: string[]
  service_id: number | null
  service_nom: string | null
}

export interface UserCreate { nom_utilisateur: string; mot_de_passe: string; role: Role; agent_id: number | null }
export interface UserUpdate { role?: Role; agent_id?: number; retirer_agent?: boolean; actif?: boolean; mot_de_passe?: string }

/** Les boutons sont masqués selon les permissions ; le vrai contrôle est fait par le backend. */
export const hasPermission = (me: Me | null, permission: string): boolean => me?.permissions.includes(permission) ?? false
