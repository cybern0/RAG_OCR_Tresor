import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router/dom'
import { ApiError } from '../shared/api/client'
import { setSignOutHandler } from '../features/auth/session'
import { ToastProvider } from '../shared/ui/Toast'
import { router } from './router'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      // pas de nouvelle tentative sur une erreur « normale » (droits, introuvable) : seulement sur un serveur injoignable
      retry: (count, error) => !(error instanceof ApiError) && count < 2,
    },
  },
})

// Fin de session : on vide le cache pour qu'un autre compte ne voie jamais les données du précédent
setSignOutHandler(() => queryClient.clear())

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>
  )
}
