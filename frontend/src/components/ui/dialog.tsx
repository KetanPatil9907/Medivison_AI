"use client"

import * as React from "react"
import { X } from "lucide-react"

import { cn } from "@/lib/utils"

interface DialogContextValue {
  open: boolean
  onOpen: () => void
  onClose: () => void
}

const DialogContext = React.createContext<DialogContextValue | null>(null)

function useDialog() {
  const ctx = React.useContext(DialogContext)
  if (!ctx) throw new Error("Dialog components must be used within <Dialog>")
  return ctx
}

export function Dialog({
  open: openProp,
  onOpenChange,
  children,
}: {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children: React.ReactNode
}) {
  const [openInternal, setOpenInternal] = React.useState(false)
  const open = openProp ?? openInternal
  const setOpen = React.useCallback(
    (next: boolean) => {
      if (onOpenChange) onOpenChange(next)
      else setOpenInternal(next)
    },
    [onOpenChange],
  )

  React.useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", onKey)
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = ""
    }
  }, [open, setOpen])

  if (!open) return null
  return (
    <DialogContext.Provider value={{ open, onOpen: () => setOpen(true), onClose: () => setOpen(false) }}>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        onMouseDown={(e) => {
          if (e.target === e.currentTarget) setOpen(false)
        }}
      >
        {children}
      </div>
    </DialogContext.Provider>
  )
}

export function DialogContent({ className, children }: { className?: string; children: React.ReactNode }) {
  const { onClose } = useDialog()
  return (
    <div
      className={cn(
        "relative z-50 grid w-full max-w-lg gap-4 border bg-white p-6 shadow-lg rounded-xl",
        className,
      )}
    >
      <button
        type="button"
        onClick={onClose}
        className="absolute right-4 top-4 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:outline-none"
        aria-label="Close"
      >
        <X className="h-4 w-4" />
      </button>
      {children}
    </div>
  )
}

export function DialogHeader({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("flex flex-col space-y-1.5 text-left", className)}>{children}</div>
}

export function DialogTitle({ className, children }: { className?: string; children: React.ReactNode }) {
  return <h2 className={cn("text-lg font-semibold leading-none tracking-tight", className)}>{children}</h2>
}

export function DialogDescription({ className, children }: { className?: string; children: React.ReactNode }) {
  return <p className={cn("text-sm text-muted-foreground", className)}>{children}</p>
}

export function DialogFooter({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("flex flex-col-reverse gap-2 sm:flex-row sm:justify-end", className)}>{children}</div>
}

function injectClick(
  children: React.ReactNode,
  handler: React.MouseEventHandler<HTMLButtonElement>,
): React.ReactElement {
  const child = React.Children.only(children) as React.ReactElement<{
    onClick?: React.MouseEventHandler<HTMLButtonElement>
  }>
  const original = child.props.onClick
  return React.cloneElement(child, {
    onClick: (e: React.MouseEvent<HTMLButtonElement>) => {
      original?.(e)
      handler(e)
    },
  })
}

export function DialogTrigger({ children, asChild }: { children: React.ReactNode; asChild?: boolean }) {
  const { onOpen } = useDialog()
  return injectClick(children, onOpen)
}

export function DialogClose({ children, asChild }: { children: React.ReactNode; asChild?: boolean }) {
  const { onClose } = useDialog()
  return injectClick(children, onClose)
}