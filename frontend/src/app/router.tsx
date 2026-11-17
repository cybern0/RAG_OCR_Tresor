// Table des routes de l'application monopage. Chaque page est chargée à la demande (découpage du code) ;
// les pages d'administration sont derrière une garde de permission.
import { createBrowserRouter, redirect } from 'react-router'
import type { RouteObject } from 'react-router'
import { Component as NotFound, ErrorPage } from './ErrorPage'
import { RequireAuth, RequireIntermediateAdmin, RequirePermission } from './guards'

const guarded = (any: string[], children: RouteObject[]): RouteObject => ({
  element: <RequirePermission any={any} />,
  children,
})

export const router = createBrowserRouter([
  {
    errorElement: <ErrorPage />,
    children: [
      { path: '/connexion', lazy: () => import('../features/auth/LoginPage') },
      {
        element: <RequireAuth />,
        children: [
          {
            lazy: () => import('./layouts/AppLayout'),
            children: [
              { index: true, lazy: () => import('../features/accueil/AccueilPage') },
              guarded(['utilisateur.lister', 'classement.gerer'], [{ path: 'roles', lazy: () => import('../features/roles/RolesPage') }]),
              {
                path: 'historique',
                element: <RequireIntermediateAdmin />,
                children: [{ index: true, lazy: () => import('../features/historique/HistoriquePage') }],
              },
              {
                path: 'securite',
                element: <RequireIntermediateAdmin />,
                children: [{ index: true, lazy: () => import('../features/securite/MotsDePassePage') }],
              },
              { path: 'profil', lazy: () => import('../features/auth/ProfilePage') },
              guarded(['document.lister'], [
                { path: 'dossiers', lazy: () => import('../features/dossiers/DossiersPage') },
                { path: 'dossiers/:dossierId', lazy: () => import('../features/dossiers/DossierPage') },
                { path: 'dossiers/:dossierId/fichiers/:documentId', lazy: () => import('../features/documents/DocumentPage') },
              ]),
              guarded(['chat.utiliser'], [
                // un seul objet de route : passer de /chat à /chat/12 ne démonte pas la page (le flux en cours continue)
                { path: 'chat/:conversationId?', lazy: () => import('../features/chat/ChatPage') },
              ]),
              guarded(['statistiques.globales'], [{ path: 'admin', lazy: () => import('../features/admin/stats/StatsPage') }]),
              guarded(['utilisateur.lister'], [
                { path: 'admin/utilisateurs', lazy: () => import('../features/admin/users/UsersPage') },
                { path: 'admin/utilisateurs/:userId', lazy: () => import('../features/admin/users/UserDetailPage') },
              ]),
              guarded(['structure.gerer'], [
                { path: 'admin/agents', lazy: () => import('../features/admin/structure/AgentsPage') },
                { path: 'admin/structure', lazy: () => import('../features/admin/structure/StructurePage') },
              ]),
              guarded(['utilisateur.lister', 'classement.gerer'], [{ path: 'admin/classement', loader: () => redirect('/roles?tab=classement') }]),
              guarded(['audit.consulter'], [{ path: 'admin/audit', loader: () => redirect('/historique') }]),
              { path: '*', Component: NotFound },
            ],
          },
        ],
      },
    ],
  },
])
