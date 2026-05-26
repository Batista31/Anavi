import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import './index.css'
import Home   from './pages/Home'
import Upload from './pages/Upload'
import Viewer from './pages/Viewer'

/** Wraps routes in a keyed div so every navigation triggers the page-enter animation */
function AnimatedRoutes() {
  const location = useLocation()
  return (
    <div key={location.pathname} className="page-enter">
      <Routes>
        <Route path="/"       element={<Home />}   />
        <Route path="/upload" element={<Upload />} />
        <Route path="/viewer" element={<Viewer />} />
      </Routes>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AnimatedRoutes />
    </BrowserRouter>
  </React.StrictMode>,
)
