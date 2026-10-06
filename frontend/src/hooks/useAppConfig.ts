import { useQuery } from '@tanstack/react-query'

import { fetchAppConfig } from '../api/cloudwatch'

export function useAppConfig() {
  return useQuery({ queryKey: ['app-config'], queryFn: fetchAppConfig, staleTime: 60_000 })
}
