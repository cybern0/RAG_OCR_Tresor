// Types de l'administration : structure, journal d'audit, classement, statistiques.
export interface Direction { id: number; code: string; nom: string; actif: boolean }
export interface ServiceItem { id: number; code: string; nom: string; site: string | null; actif: boolean; direction_id: number; direction_nom: string }
export interface DivisionItem { id: number; code: string | null; nom: string; actif: boolean; service_id: number; service_nom: string | null; direction_nom: string | null }
export interface Agent {
  id: number; matricule: string; nom: string; prenom: string; fonction: string | null; email: string | null
  service_id: number | null; service_nom: string | null; division_id: number | null; division_nom: string | null; titre: 'CHEF_DIVISION' | 'CHEF_SERVICE' | null; actif: boolean; nom_utilisateur: string | null
}
export interface AuditRow {
  id: number; cree_le: string; nom_utilisateur: string | null; action: string; entite: string | null
  entite_id: number | null; detail: Record<string, unknown>; adresse_ip: string | null
}

export interface CategoryItem { id: number; parent_id: number | null; nom: string; couleur: string | null; ordre: number; actif: boolean }
export interface TypeItem { id: number; nom: string; actif: boolean }
export interface TagItem { id: number; nom: string }
export interface RuleItem {
  id: number; nom: string; priorite: number; actif: boolean; critere: unknown
  categorie_id: number | null; type_document_id: number | null; tags: string[]; confidentialite: string | null
}
export interface SimulationResult { categorie_id: number | null; type_document_id: number | null; tags: string[]; confidentialite: string | null }

/** Ligne groupée des statistiques : le serveur fournit le libellé (nom), jamais seulement un numéro. */
export interface StatLine { total: number; nom: string | null; couleur?: string | null; categorie_id?: number; type_document_id?: number; service_id?: number; direction_id?: number }
export interface DashboardStats {
  total_documents: number; actifs: number; corbeille: number; sans_classement: number; stockage_octets: number; nb_versions: number
  statut: Record<string, number>
  par_categorie: StatLine[]; par_type: StatLine[]; par_service: StatLine[]; par_direction: StatLine[]
  par_confidentialite: Record<string, number>; par_extension: Record<string, number>
}

export interface Health { status: string; api: boolean; [key: string]: unknown }
