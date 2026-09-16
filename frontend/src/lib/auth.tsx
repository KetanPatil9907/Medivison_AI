"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import {
  currentUser,
  login as apiLogin,
  logout as apiLogout,
  registerDoctor as apiRegisterDoctor,
  registerPatient as apiRegisterPatient,
} from "@/lib/api"
import type { UserPublic, UserRole } from "@/lib/types"

interface AuthContextValue {
  user: UserPublic | null
  loading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<UserPublic>
  registerPatient: (payload: Record<string, unknown>) => Promise<UserPublic>
  registerDoctor: (payload: Record<string, unknown>) => Promise<Record<string, unknown>>
  logout: () => void
  hasRole: (...roles: UserRole[]) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    setUser(currentUser())
    setLoading(false)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const u = await apiLogin(email, password)
    setUser(u)
    return u
  }, [])

  const registerPatient = useCallback(async (payload: Record<string, unknown>) => {
    const u = await apiRegisterPatient(payload)
    setUser(u)
    return u
  }, [])

  const registerDoctor = useCallback(
    async (payload: Record<string, unknown>) => apiRegisterDoctor(payload),
    [],
  )

  const logout = useCallback(() => {
    apiLogout()
    setUser(null)
    router.push("/login")
  }, [router])

  const hasRole = useCallback(
    (...roles: UserRole[]) => (user ? roles.includes(user.role) : false),
    [user],
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      isAuthenticated: !!user,
      login,
      registerPatient,
      registerDoctor,
      logout,
      hasRole,
    }),
    [user, loading, login, registerPatient, registerDoctor, logout, hasRole],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}