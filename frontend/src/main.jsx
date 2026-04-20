import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './ui'          // design-system tokens load first so index.css can override if needed
import './index.css'
import App from './App.jsx'
import { installConsoleCapture } from './utils/consoleBuffer.js'

installConsoleCapture();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
