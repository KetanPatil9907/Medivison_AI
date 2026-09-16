"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

import { Spinner } from "@/components/ui/spinner"
import { useAuth } from "@/lib/auth"
import type { UserRole } from "@/lib/types"

export function AuthGate({ roles, children }: { roles?: UserRole[]; children: React.ReactNode }) {
  const { user, loading, isAuthenticated } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (loading) return
    if (!isAuthenticated) {
      router.replace("/login")
      return
    }
    if (roles && roles.length > 0 && user && !roles.includes(user.role)) {
      router.replace("/dashboard")
    }
  }, [loading, isAuthenticated, user, roles, router])

  if (loading || !isAuthenticated) return <Spinner className="min-h-screen" />
  return <>{children}</>
}