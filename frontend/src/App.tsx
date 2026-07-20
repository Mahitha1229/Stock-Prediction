import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'

export default function App() {
  const { token } = useAuth()
  return token ? <Dashboard /> : <Login />
}