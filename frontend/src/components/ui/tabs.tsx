"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

interface TabsContextValue {
  value: string
  onSelect: (value: string) => void
}

const TabsContext = React.createContext<TabsContextValue | null>(null)

function useTabs() {
  const ctx = React.useContext(TabsContext)
  if (!ctx) throw new Error("Tabs components must be used within <Tabs>")
  return ctx
}

export function Tabs({
  defaultValue,
  value,
  onValueChange,
  className,
  children,
}: {
  defaultValue?: string
  value?: string
  onValueChange?: (value: string) => void
  className?: string
  children: React.ReactNode
}) {
  const [internal, setInternal] = React.useState<string>(defaultValue ?? "")
  const current = value ?? internal
  const onSelect = React.useCallback(
    (v: string) => {
      if (value === undefined) setInternal(v)
      onValueChange?.(v)
    },
    [value, onValueChange],
  )
  return (
    <TabsContext.Provider value={{ value: current, onSelect }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  )
}

export function TabsList({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("inline-flex h-10 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground", className)}>
      {children}
    </div>
  )
}

export function TabsTrigger({
  value,
  className,
  children,
}: {
  value: string
  className?: string
  children: React.ReactNode
}) {
  const { value: current, onSelect } = useTabs()
  const active = current === value
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={() => onSelect(value)}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
        active && "bg-background text-foreground shadow",
      )}
    >
      {children}
    </button>
  )
}

export function TabsContent({
  value,
  className,
  children,
}: {
  value: string
  className?: string
  children: React.ReactNode
}) {
  const { value: current } = useTabs()
  if (current !== value) return null
  return (
    <div role="tabpanel" className={cn("mt-4", className)}>
      {children}
    </div>
  )
}