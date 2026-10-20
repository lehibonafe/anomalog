import { apiClient } from './client'
import type { InvestigationListResponse, SavedInvestigation } from './types'

export async function fetchInvestigations(offset = 0): Promise<InvestigationListResponse> {
  const { data } = await apiClient.get<InvestigationListResponse>('/api/investigations', {
    params: { offset, limit: 50 },
  })
  return data
}

export async function saveInvestigation(record: SavedInvestigation): Promise<SavedInvestigation> {
  const { data } = await apiClient.put<SavedInvestigation>(
    `/api/investigations/${encodeURIComponent(record.id)}`,
    record,
  )
  return data
}

export async function importInvestigations(records: SavedInvestigation[]): Promise<void> {
  await apiClient.post('/api/investigations/import', { items: records })
}

export async function removeInvestigation(id: string): Promise<void> {
  await apiClient.delete(`/api/investigations/${encodeURIComponent(id)}`)
}
