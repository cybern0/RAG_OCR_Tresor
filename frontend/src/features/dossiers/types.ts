// Types des dossiers d'une division (un seul niveau, créés par le super administrateur). Un dossier n'a ni rôle ni mot de passe
// propre : l'accès aux fichiers se règle par rôle de division (voir features/roles) ; le serveur reste la seule autorité (404 / 403).
export interface Dossier {
  id: number; division_id: number; division_nom: string; nom: string; description: string | null
  archive: boolean; cree_par_nom: string | null; cree_le: string; modifie_le: string
  nb_fichiers: number; nb_fichiers_masques: number; peut_modifier: boolean; peut_creer: boolean
}
