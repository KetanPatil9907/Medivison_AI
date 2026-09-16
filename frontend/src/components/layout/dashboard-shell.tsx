"use client"

import { useState } from "react"
import { LogOut, Menu, X } from "lucide-react"
import { toast } from "@/components/ui/toast"

import { SidebarContent } from "@/components/layout/sidebar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"
import { ROLE_LABEL } from "@/lib/nav"
import { initials } from "@/lib/utils"

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const [drawerOpen, setDrawerOpen] = useState(false)

  if (!user) return null

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-card lg:flex">
        <SidebarContent />
      </aside>

      {drawerOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawerOpen(false)} />
          <aside className="absolute left-0 top-0 flex h-full w-72 flex-col border-r bg-card">
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              className="absolute right-3 top-4 rounded-md p-1 text-muted-foreground hover:bg-muted"
              aria-label="Close menu"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setDrawerOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b bg-background/95 px-4 py-3 backdrop-blur sm:px-6">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="-ml-2 rounded-md p-2 text-muted-foreground hover:bg-muted lg:hidden"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="flex items-center gap-3 sm:ml-auto">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium leading-tight">{user.full_name}</p>
              <p className="text-xs leading-tight text-muted-foreground">{ROLE_LABEL[user.role] ?? user.role}</p>
            </div>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-secondary-foreground">
              {initials(user.full_name)}
            </span>
            <Badge variant="info" className="hidden sm:inline-flex">
              {ROLE_LABEL[user.role] ?? user.role}
            </Badge>
            <Button variant="ghost" size="icon" onClick={() => { logout(); toast.info("Signed out") }} aria-label="Sign out">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>

        <footer className="border-t px-6 py-4 text-center text-xs text-muted-foreground">
          MediVision AI · Demo platform — not a substitute for professional medical advice.
        </footer>
      </div>
    </div>
  )
}