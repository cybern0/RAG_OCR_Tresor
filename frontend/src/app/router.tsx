// Table des routes de l'application monopage. Chaque page est chargée à la demande (découpage du code) ;
// les pages d'administration sont derrière une garde de permission.
import { createBrowserRouter } from 'react-router'
import type { RouteObject } from 'react-router'
import { Component as NotFound, ErrorPage } from './ErrorPage'
import { Home, RequireAuth, RequirePermission } from './guards'

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
              { index: true, element: <Home /> },
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
              guarded(['dossier.gerer'], [
                { path: 'admin/dossiers', lazy: () => import('../features/admin/dossiers/AdminDossiersPage') },
                { path: 'admin/demandes', lazy: () => import('../features/admin/demandes/DemandesPage') },
              ]),
              guarded(['utilisateur.lister'], [
                { path: 'admin/utilisateurs', lazy: () => import('../features/admin/users/UsersPage') },
                { path: 'admin/utilisateurs/:userId', lazy: () => import('../features/admin/users/UserDetailPage') },
              ]),
              guarded(['structure.gerer'], [
                { path: 'admin/agents', lazy: () => import('../features/admin/structure/AgentsPage') },
                { path: 'admin/structure', lazy: () => import('../features/admin/structure/StructurePage') },
              ]),
              guarded(['classement.gerer'], [{ path: 'admin/classement', lazy: () => import('../features/admin/classement/ClassementPage') }]),
              guarded(['audit.consulter'], [{ path: 'admin/audit', lazy: () => import('../features/admin/audit/AuditPage') }]),
              { path: '*', Component: NotFound },
            ],
          },
        ],
      },
    ],
  },
])
