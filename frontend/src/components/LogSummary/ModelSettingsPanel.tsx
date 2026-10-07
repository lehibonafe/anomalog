import anthropicLogo from '@lobehub/icons-static-svg/icons/anthropic.svg'
import geminiLogo from '@lobehub/icons-static-svg/icons/gemini-color.svg'
import liteLlmLogo from '@lobehub/icons-static-svg/icons/llmapi-color.svg'
import ollamaLogo from '@lobehub/icons-static-svg/icons/ollama.svg'
import openAiLogo from '@lobehub/icons-static-svg/icons/openai.svg'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

import { useTestConnection } from '../../hooks/useTestConnection'
import { DEFAULT_LLM_MODELS, type LlmProvider, useSelectionStore } from '../../state/selectionStore'
import { modelDestination } from '../../utils/modelDestination'

interface ProviderOption {
  value: LlmProvider
  label: string
  description: string
  logo: string
  monochrome?: boolean
}

const PROVIDERS: ProviderOption[] = [
  { value: 'gemini', label: 'Gemini', description: 'Google AI', logo: geminiLogo },
  { value: 'openai', label: 'OpenAI', description: 'OpenAI API', logo: openAiLogo, monochrome: true },
  { value: 'anthropic', label: 'Anthropic', description: 'Claude models', logo: anthropicLogo, monochrome: true },
  { value: 'ollama', label: 'Ollama', description: 'Local runtime', logo: ollamaLogo, monochrome: true },
  { value: 'litellm', label: 'LiteLLM', description: 'Team proxy', logo: liteLlmLogo },
]

function ProviderLogo({ provider }: { provider: ProviderOption }) {
  return (
    <span className='model-provider-logo-frame' aria-hidden='true'>
      <img
        className={`model-provider-logo${provider.monochrome ? ' monochrome' : ''}`}
        src={provider.logo}
        alt=''
      />
    </span>
  )
}

function ProviderSelect({
  value,
  onChange,
}: {
  value: LlmProvider
  onChange: (provider: LlmProvider) => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([])
  const selectedIndex = Math.max(0, PROVIDERS.findIndex((provider) => provider.value === value))
  const selectedProvider = PROVIDERS[selectedIndex]

  function openMenu(focusIndex = selectedIndex) {
    setIsOpen(true)
    window.requestAnimationFrame(() => optionRefs.current[focusIndex]?.focus())
  }

  function selectProvider(provider: LlmProvider) {
    onChange(provider)
    setIsOpen(false)
    window.requestAnimationFrame(() => triggerRef.current?.focus())
  }

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      openMenu(event.key === 'ArrowUp' ? PROVIDERS.length - 1 : selectedIndex)
    }
  }

  function handleOptionKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key === 'Escape') {
      event.preventDefault()
      setIsOpen(false)
      triggerRef.current?.focus()
      return
    }

    const targetIndex = event.key === 'ArrowDown'
      ? (index + 1) % PROVIDERS.length
      : event.key === 'ArrowUp'
        ? (index - 1 + PROVIDERS.length) % PROVIDERS.length
        : event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? PROVIDERS.length - 1
            : null

    if (targetIndex !== null) {
      event.preventDefault()
      optionRefs.current[targetIndex]?.focus()
    }
  }

  return (
    <div
      className='model-settings-field'
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setIsOpen(false)
      }}
    >
      <span id='model-provider-label'>Provider</span>
      <div className='model-provider-select'>
        <button
          ref={triggerRef}
          type='button'
          className='model-provider-select-trigger'
          aria-labelledby='model-provider-label model-provider-value'
          aria-haspopup='listbox'
          aria-expanded={isOpen}
          aria-controls='model-provider-options'
          onKeyDown={handleTriggerKeyDown}
          onClick={() => (isOpen ? setIsOpen(false) : openMenu())}
        >
          <ProviderLogo provider={selectedProvider} />
          <span id='model-provider-value' className='model-provider-select-value'>
            <strong>{selectedProvider.label}</strong>
            <small>{selectedProvider.description}</small>
          </span>
          <svg className='model-provider-select-chevron' viewBox='0 0 16 16' aria-hidden='true'>
            <path d='m4 6 4 4 4-4' />
          </svg>
        </button>

        {isOpen && (
          <div id='model-provider-options' className='model-provider-options' role='listbox' aria-labelledby='model-provider-label'>
            {PROVIDERS.map((provider, index) => (
              <button
                ref={(element) => { optionRefs.current[index] = element }}
                type='button'
                role='option'
                aria-selected={provider.value === value}
                className='model-provider-option'
                key={provider.value}
                onKeyDown={(event) => handleOptionKeyDown(event, index)}
                onClick={() => selectProvider(provider.value)}
              >
                <ProviderLogo provider={provider} />
                <span>
                  <strong>{provider.label}</strong>
                  <small>{provider.description}</small>
                </span>
                {provider.value === value && <span className='model-provider-check' aria-hidden='true'>✓</span>}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function ModelSettingsPanel() {
  const llmProvider = useSelectionStore((s) => s.llmProvider);
  const setLlmProvider = useSelectionStore((s) => s.setLlmProvider);
  const llmApiKey = useSelectionStore((s) => s.llmApiKey);
  const setLlmApiKey = useSelectionStore((s) => s.setLlmApiKey);
  const llmModel = useSelectionStore((s) => s.llmModel);
  const setLlmModel = useSelectionStore((s) => s.setLlmModel);
  const llmBaseUrl = useSelectionStore((s) => s.llmBaseUrl);
  const setLlmBaseUrl = useSelectionStore((s) => s.setLlmBaseUrl);
  const testConnection = useTestConnection()
  const resetTestConnection = testConnection.reset

  useEffect(() => {
    resetTestConnection()
  }, [llmProvider, llmApiKey, llmModel, llmBaseUrl, resetTestConnection])

  return (
    <div className='model-settings-panel'>
      <ProviderSelect value={llmProvider} onChange={setLlmProvider} />

      <label className="model-settings-field">
        {llmProvider === "ollama" ? "API key (usually not required)" : "API key"}
        <input
          type="password"
          placeholder={
            llmProvider === "gemini" || llmProvider === "litellm"
              ? "Uses server default if blank"
              : "Required"
          }
          value={llmApiKey}
          onChange={(e) => setLlmApiKey(e.target.value)}
          autoComplete="off"
        />
      </label>

      <label className="model-settings-field">
        Model
        <input
          type="text"
          placeholder={`${DEFAULT_LLM_MODELS[llmProvider]} (default)`}
          value={llmModel}
          onChange={(e) => setLlmModel(e.target.value)}
        />
      </label>

      {llmProvider === "ollama" && (
        <label className="model-settings-field">
          Base URL
          <input
            type="text"
            placeholder="http://localhost:11434/v1"
            value={llmBaseUrl}
            onChange={(e) => setLlmBaseUrl(e.target.value)}
          />
          {/* If the backend runs in Docker and Ollama runs on the host,
              "localhost" inside the container won't reach the host — use
              host.docker.internal instead. */}
        </label>
      )}

      {llmProvider === "litellm" && (
        <label className="model-settings-field">
          Base URL
          <input
            type="text"
            placeholder="http://llm.etapinc.com/v1 (default if blank)"
            value={llmBaseUrl}
            onChange={(e) => setLlmBaseUrl(e.target.value)}
          />
        </label>
      )}

      <p className="hint">Connection tests and analysis send requests to {modelDestination(llmProvider, llmBaseUrl)}. Custom URLs require server approval.</p>

      <button
        type="button"
        className="btn-block"
        disabled={testConnection.isPending}
        onClick={() => testConnection.mutate()}
      >
        {testConnection.isPending && <span className="spinner" />}
        {testConnection.isPending ? "Testing..." : "Test connection"}
      </button>
      {testConnection.isSuccess && (
        <p className={testConnection.data.success ? "success-text" : "error-text"}>
          {testConnection.data.success
            ? `Connected (model: ${testConnection.data.model})`
            : testConnection.data.message}
        </p>
      )}
      {testConnection.isError && (
        <p className="error-text">Test failed. Check the backend logs.</p>
      )}
    </div>
  );
}
