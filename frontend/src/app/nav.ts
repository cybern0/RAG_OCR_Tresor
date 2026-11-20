// Navigation principale : une entrée par page, avec les permissions qui l'ouvrent. La même table sert à la barre latérale,
// aux gardes de routes et à la page d'accueil par défaut. Le super administrateur n'a pas d'Accueil : il arrive
// directement sur son tableau de bord /admin (il n'a accès ni aux fichiers ni à l'assistant).
import { BarChart3, Building2, FileText, FileUser, History, Home, Shield, MessageSquare, Users, UserSquare } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface NavItem { to: string; label: string; icon: LucideIcon; any: string[]; end?: boolean; rootOnly?: boolean; niveaux?: string[] }

export const MAIN_NAV: NavItem[] = [
  // pas de statistiques.globales ici : le super administrateur n'a pas d'Accueil, il arrive sur /admin
  { to: '/', label: 'Accueil', icon: Home, any: ['document.lister', 'chat.utiliser'], end: true },
  { to: '/fichiers', label: 'Fichiers', icon: FileText, any: ['document.lister'] },
  { to: '/chat', label: 'Assistant', icon: MessageSquare, any: ['chat.utiliser'] },
]

export const INTERMEDIATE_NAV: NavItem[] = [
  // l'historique est de l'administration : le super administrateur l'a aussi, alors qu'il ne liste pas les fichiers
  { to: '/historique', label: 'Historique', icon: History, any: ['document.lister', 'audit.consulter'] },
]

export const ADMIN_NAV: NavItem[] = [
  { to: '/admin', label: 'Tableau de bord', icon: BarChart3, any: ['statistiques.globales'], end: true },
  { to: '/roles', label: 'Rôles', icon: Shield, any: ['utilisateur.lister', 'classement.gerer'] },
  // affectation des fichiers aux agents : chef de service et chef de division seulement (pas le super administrateur)
  { to: '/affectation', label: 'Affectation', icon: FileUser, any: ['utilisateur.lister', 'classement.gerer'], niveaux: ['SERVICE', 'DIVISION'] },
  { to: '/admin/utilisateurs', label: 'Utilisateurs', icon: Users, any: ['utilisateur.lister'] },
  // la gestion des agents (personnes) et de la structure (directions, services, divisions) reste au
  // super administrateur : le chef de service a les MÊMES menus que le chef de division — il gère les
  // comptes et les rôles via /admin/utilisateurs, /roles et /affectation
  { to: '/admin/agents', label: 'Agents', icon: UserSquare, any: ['structure.gerer'], rootOnly: true },
  { to: '/admin/structure', label: 'Directions, services et divisions', icon: Building2, any: ['structure.gerer'], rootOnly: true },
]

export const allowed = (item: NavItem, can: (p: string) => boolean, niveau?: string | null) =>
  item.any.some(can) && (!item.rootOnly || niveau === 'ROOT') && (!item.niveaux || (!!niveau && item.niveaux.includes(niveau)))

export const isIntermediateAdmin = (user: { niveau?: string | null; role?: string | null } | null): boolean => {
  if (!user) return false
  return user.niveau === 'ROOT' || user.niveau === 'SERVICE' || user.niveau === 'DIVISION' || user.role === 'ADMIN'
}

/** Première page accessible au compte (page d'accueil). Le super administrateur arrive sur /admin. */
export function homePath(can: (p: string) => boolean, niveau?: string | null): string | null {
  return [...MAIN_NAV.filter((i) => i.to !== '/'), ...ADMIN_NAV].find((i) => allowed(i, can, niveau))?.to ?? null
}
