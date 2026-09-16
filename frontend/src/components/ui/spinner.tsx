import * as React from "react"
import { Loader2 } from "lucide-react"

import { cn } from "@/lib/utils"

export function Spinner({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center justify-center p-8", className)}>
      <Loader2 className="h-6 w-6 animate-spin text-primary" />
      <span className="sr-only">Loading…</span>
    </div>
  )
}