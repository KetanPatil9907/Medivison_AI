import * as React from "react"
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react"

import { cn } from "@/lib/utils"

const variants = {
  default: { icon: Info, className: "border-border bg-muted/40 text-foreground" },
  destructive: { icon: XCircle, className: "border-rose-200 bg-rose-50 text-rose-800" },
  warning: { icon: AlertTriangle, className: "border-amber-200 bg-amber-50 text-amber-800" },
  success: { icon: CheckCircle2, className: "border-emerald-200 bg-emerald-50 text-emerald-800" },
} as const

interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: keyof typeof variants
  title?: string
  children?: React.ReactNode
}

export function Alert({ variant = "default", title, className, children, ...props }: AlertProps) {
  const { icon: Icon, className: tone } = variants[variant]
  return (
    <div role="alert" className={cn("flex gap-3 rounded-lg border p-4 text-sm", tone, className)} {...props}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 space-y-1">
        {title ? <p className="font-medium leading-none">{title}</p> : null}
        {children ? <div className="leading-relaxed opacity-90">{children}</div> : null}
      </div>
    </div>
  )
}