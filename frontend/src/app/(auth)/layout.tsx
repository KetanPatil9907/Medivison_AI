import type { Metadata } from "next"

import { AuthLayout } from "@/components/auth-layout"
import { Toaster } from "@/components/ui/toast"

export function generateMetadata(): Metadata {
  return { title: "Sign in" }
}

export default function AuthPagesLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthLayout>
      {children}
      <Toaster />
    </AuthLayout>
  )
}