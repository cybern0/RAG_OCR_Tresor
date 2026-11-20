// Division sur laquelle porte la page : le super administrateur choisit parmi toutes les divisions ; le chef de
// service parmi celles de SON service (le serveur renvoie déjà la liste scopée) ; le chef de division voit la sienne, fixe.
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuth } from '../auth/session'
import { listDivisions } from './api'

export function useDivisionChoisie() {
  const { user } = useAuth()
  const peutChoisir = user?.niveau === 'ROOT' || user?.niveau === 'SERVICE'
  const divisions = useQuery({ queryKey: ['divisions'], queryFn: listDivisions, enabled: peutChoisir })
  const [choix, setChoix] = useState<number | null>(null)
  const divisionId = choix ?? user?.division_id ?? divisions.data?.[0]?.id ?? null
  return { peutChoisir, divisions, divisionId, choisir: setChoix }
}
