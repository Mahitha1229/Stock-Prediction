import { createContext, useContext, useState, ReactNode } from 'react'
import { login as apiLogin } from '../api'

interface AuthContextType {
  token: string | null
  username: string | null
  loginUser: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))
  const [username, setUsername] = useState<string | null>(localStorage.getItem('username'))

  async function loginUser(user: string, password: string) {
    const t = await apiLogin(user, password)
    localStorage.setItem('token', t)
    localStorage.setItem('username', user)
    setToken(t)
    setUsername(user)
  }

  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    setToken(null)
    setUsername(null)
  }

  return (
    <AuthContext.Provider value={{ token, username, loginUser, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}