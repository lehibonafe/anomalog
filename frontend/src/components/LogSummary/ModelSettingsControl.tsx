import { useEffect, useRef, useState, type MouseEvent } from 'react'

import { useSelectionStore } from '../../state/selectionStore'
import { ModelSettingsPanel } from './ModelSettingsPanel'

export function ModelSettingsControl() {
  const llmProvider = useSelectionStore((state) => state.llmProvider)
  const llmApiKey = useSelectionStore((state) => state.llmApiKey)
  const llmModel = useSelectionStore((state) => state.llmModel)
  const llmBaseUrl = useSelectionStore((state) => state.llmBaseUrl)
  const dialogRef = useRef<HTMLDialogElement | null>(null)
  const [isOpen, setIsOpen] = useState(false)

  const isCustomModel = llmProvider !== 'litellm' || !!llmApiKey || !!llmModel || !!llmBaseUrl

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return

    if (isOpen && !dialog.open) {
      dialog.showModal()
      window.requestAnimationFrame(() => dialog.querySelector<HTMLElement>('.model-provider-select-trigger')?.focus())
    } else if (!isOpen && dialog.open) {
      dialog.close()
    }
  }, [isOpen])

  function closeDialog() {
    setIsOpen(false)
  }

  function closeFromBackdrop(event: MouseEvent<HTMLDialogElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    const isOutside = event.clientX < bounds.left
      || event.clientX > bounds.right
      || event.clientY < bounds.top
      || event.clientY > bounds.bottom
    if (isOutside) closeDialog()
  }

  return (
    <div className='app-model-settings'>
      <span className='app-model-provider'>
        {llmProvider}{isCustomModel ? ' · custom' : ' · default'}
      </span>
      <button
        type='button'
        aria-expanded={isOpen}
        aria-controls='model-settings-dialog'
        aria-haspopup='dialog'
        onClick={() => setIsOpen(true)}
      >
        Model settings
      </button>

      <dialog
        ref={dialogRef}
        id='model-settings-dialog'
        className='model-settings-dialog'
        aria-labelledby='model-settings-title'
        onCancel={closeDialog}
        onClose={closeDialog}
        onClick={closeFromBackdrop}
      >
        <div className='model-settings-dialog-header'>
          <div>
            <h2 id='model-settings-title'>Model settings</h2>
            <p>Choose the AI provider and model used to summarize your logs.</p>
          </div>
          <button
            type='button'
            className='model-settings-dialog-close'
            aria-label='Close model settings'
            onClick={closeDialog}
          >
            ×
          </button>
        </div>
        <div className='model-settings-dialog-body'>
          <ModelSettingsPanel />
        </div>
      </dialog>
    </div>
  )
}
