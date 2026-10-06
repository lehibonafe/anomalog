import type { LlmProvider } from '../state/selectionStore'

export function modelDestination(provider: LlmProvider, baseUrl: string): string {
  const customUrl = baseUrl.trim()
  if (customUrl) return `${provider} at ${customUrl}`
  return provider === 'litellm'
    ? 'LiteLLM at the server configured endpoint'
    : `${provider} at its default endpoint`
}
