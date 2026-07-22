import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import { ChatProvider } from './context/ChatContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ChatPage from './pages/ChatPage'

export default function App() {
  const { token } = useAuth()

  if (!token) return <Login />

  return (
    <ChatProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ChatProvider>
  )
}