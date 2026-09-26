import './App.css'
import { Navigate, Route, Routes } from 'react-router-dom'
import NotFound from './pages/NotFound/NotFound'
import Dashboard from './pages/Dashboard/Dashboard'
import Login from './pages/Login/Login'
import { getAccessToken } from './api/client'

function ProtectedDashboard() {
  return getAccessToken() ? <Dashboard /> : <Navigate to="/login" replace />
}


function App() {

  return (
    <>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />

        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<ProtectedDashboard />} />

        <Route path="*" element={<NotFound />} />
      </Routes>
    </>
  )
}

export default App
