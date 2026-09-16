"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Activity } from "lucide-react"

import { ROLE_NAV, type NavSection } from "@/lib/nav"
import { useAuth } from "@/lib/auth"
import { cn } from "@/lib/utils"

export function Brand({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link href="/dashboard" onClick={onNavigate} className="flex items-center gap-2 px-3 py-4 font-semibold">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Activity className="h-4 w-4" />
      </span>
      MediVision AI
    </Link>
  )
}

function NavLinks({ sections, onNavigate }: { sections: NavSection[]; onNavigate?: () => void }) {
  const pathname = usePathname()
  return (
    <div className="flex-1 space-y-6 overflow-y-auto scrollbar-thin px-3 pb-6">
      {sections.map((section) => (
        <div key={section.title}>
          <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
            {section.title}
          </p>
          <ul className="space-y-0.5">
            {section.items.map((item) => {
              const href = item.href
              const active =
                pathname === href || (href !== "/dashboard" && pathname.startsWith(href))
              const Icon = item.icon
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onNavigate}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                      active
                        ? "bg-primary/10 text-primary"
                        : "text-foreground/70 hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {item.label}
                  </Link>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </div>
  )
}

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth()
  if (!user) return null
  const sections = ROLE_NAV[user.role] ?? []
  return (
    <>
      <Brand onNavigate={onNavigate} />
      <NavLinks sections={sections} onNavigate={onNavigate} />
    </>
  )
}