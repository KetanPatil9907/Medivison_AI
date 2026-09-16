import Link from "next/link"
import { Activity } from "lucide-react"

export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 to-white">
      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col px-6 py-10">
        <Link href="/" className="flex items-center justify-center gap-2 font-semibold text-slate-900">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Activity className="h-5 w-5" />
          </span>
          MediVision AI
        </Link>
        <div className="flex-1 pt-10">{children}</div>
        <p className="pb-2 pt-8 text-center text-xs text-slate-500">
          Not a substitute for professional medical advice.
        </p>
      </div>
    </div>
  )
}