// Navigation principale : une entrée par page, avec les permissions qui l'ouvrent. La même table sert à la barre latérale,
// aux gardes de routes et à la page d'accueil par défaut.
import { BarChart3, Building2, FolderOpen, Home, Inbox, KeyRound, History, Shield, MessageSquare, ScrollText, Tags, Users, UserSquare } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface NavItem { to: string; label: string; icon: LucideIcon; any: string[]; end?: boolean }

export const MAIN_NAV: NavItem[] = [
  { to: '/', label: 'Accueil', icon: Home, any: ['document.lister', 'chat.utiliser', 'statistiques.globales'], end: true },
  { to: '/dossiers', label: 'Dossiers et fichiers', icon: FolderOpen, any: ['document.lister'] },
  { to: '/demandes', label: 'Demandes d’accès', icon: Inbox, any: ['document.lister'] },
  { to: '/historique', label: 'Historique', icon: History, any: ['document.lister'] },
  { to: '/securite', label: 'Mots de passe de dossier', icon: KeyRound, any: ['document.lister'] },
  { to: '/chat', label: 'Assistant', icon: MessageSquare, any: ['chat.utiliser'] },
]

export const ADMIN_NAV: NavItem[] = [
  { to: '/admin', label: 'Tableau de bord', icon: BarChart3, any: ['statistiques.globales'], end: true },
  { to: '/roles', label: 'Rôles de division', icon: Shield, any: ['utilisateur.lister'] },
  { to: '/admin/utilisateurs', label: 'Utilisateurs', icon: Users, any: ['utilisateur.lister'] },
  { to: '/admin/agents', label: 'Agents', icon: UserSquare, any: ['structure.gerer'] },
  { to: '/admin/structure', label: 'Directions, services et divisions', icon: Building2, any: ['structure.gerer'] },
  { to: '/admin/classement', label: 'Classement', icon: Tags, any: ['classement.gerer'] },
  { to: '/admin/audit', label: 'Journal d’audit', icon: ScrollText, any: ['audit.consulter'] },
]

export const allowed = (item: NavItem, can: (p: string) => boolean) => item.any.some(can)

/** Première page accessible au compte (page d'accueil). */
export function homePath(can: (p: string) => boolean): string | null {
  return [...MAIN_NAV.filter((i) => i.to !== '/'), ...ADMIN_NAV].find((i) => allowed(i, can))?.to ?? null
}
