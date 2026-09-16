import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-destructive text-destructive-foreground",
        outline: "text-foreground",
        success: "border-transparent bg-emerald-100 text-emerald-800",
        warning: "border-transparent bg-amber-100 text-amber-800",
        info: "border-transparent bg-sky-100 text-sky-800",
        danger: "border-transparent bg-rose-100 text-rose-800",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }

export function statusVariant(status: string): VariantProps<typeof badgeVariants>["variant"] {
  const s = status.toUpperCase()
  if (["ACTIVE", "APPROVED", "CONFIRMED", "COMPLETED", "UPCOMING", "SCHEDULED"].includes(s)) return "success"
  if (["PENDING", "CHECKED_IN", "IN_PROGRESS", "PHYSICAL", "ONLINE", "BOTH"].includes(s)) return "warning"
  if (["SUSPENDED", "CANCELLED", "REJECTED", "NO_SHOW"].includes(s)) return "danger"
  if (["DISABLED", "INACTIVE", "EXPIRED"].includes(s)) return "secondary"
  return "info"
}