import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import Styleguide from './pages/Styleguide'

const isStyleguide = window.location.pathname.replace(/\/+$/, '') === '/styleguide'
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isStyleguide ? <Styleguide /> : <App />}
  </StrictMode>,
)
