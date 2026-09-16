import { AuthGate } from "@/components/auth-gate"
import { DashboardShell } from "@/components/layout/dashboard-shell"
import { Toaster } from "@/components/ui/toast"

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <DashboardShell>{children}</DashboardShell>
      <Toaster />
    </AuthGate>
  )
}