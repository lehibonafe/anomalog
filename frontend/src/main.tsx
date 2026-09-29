import { QueryClientProvider } from '@tanstack/react-query'
import '@fontsource/roboto-condensed/latin-400.css'
import '@fontsource/roboto-condensed/latin-400-italic.css'
import '@fontsource/roboto-condensed/latin-500.css'
import '@fontsource/roboto-condensed/latin-600.css'
import '@fontsource/roboto-condensed/latin-700.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { queryClient } from './state/queryClient.ts'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
