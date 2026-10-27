import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import KisApp from './KisApp'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>{window.location.pathname === '/demo-kis' ? <KisApp /> : <App />}</React.StrictMode>,
)
