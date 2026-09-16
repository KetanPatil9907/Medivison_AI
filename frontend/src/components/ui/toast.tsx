"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, Info, XCircle } from "lucide-react"

import { cn } from "@/lib/utils"

type ToastKind = "success" | "error" | "info"

interface ToastItem {
  id: number
  kind: ToastKind
  message: string
}

type Listener = (toasts: ToastItem[]) => void

let toasts: ToastItem[] = []
let listeners = new Set<Listener>()
let nextId = 1

function emit() {
  listeners.forEach((l) => l([...toasts]))
}

function push(kind: ToastKind, message: string) {
  const id = nextId++
  toasts = [...toasts, { id, kind, message }]
  emit()
  setTimeout(() => dismiss(id), 4500)
}

export function dismiss(id: number) {
  toasts = toasts.filter((t) => t.id !== id)
  emit()
}

export const toast = {
  success: (message: string) => push("success", message),
  error: (message: string) => push("error", message),
  info: (message: string) => push("info", message),
}

const icons = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
}

const tones: Record<ToastKind, string> = {
  success: "border-emerald-200 bg-white text-emerald-800",
  error: "border-rose-200 bg-white text-rose-800",
  info: "border-sky-200 bg-white text-sky-800",
}

export function Toaster() {
  const [items, setItems] = useState<ToastItem[]>([])

  useEffect(() => {
    const listener: Listener = (next) => setItems(next)
    listeners.add(listener)
    emit()
    return () => {
      listeners.delete(listener)
    }
  }, [])

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
      {items.map((t) => {
        const Icon = icons[t.kind]
        return (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto flex items-start gap-2 rounded-lg border p-3 text-sm shadow-lg",
              tones[t.kind],
            )}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0" />
            <span className="min-w-0 flex-1">{t.message}</span>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="rounded p-0.5 opacity-60 hover:opacity-100"
              aria-label="Dismiss"
            >
              <XCircle className="h-4 w-4" />
            </button>
          </div>
        )
      })}
    </div>
  )
}