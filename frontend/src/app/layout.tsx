import type { Metadata } from "next"

import { AuthProvider } from "@/lib/auth"
import { cn } from "@/lib/utils"

import "./globals.css"

export const metadata: Metadata = {
  title: {
    default: "MediVision AI",
    template: "%s · MediVision AI",
  },
  description:
    "AI-assisted healthcare platform — symptom analysis, risk prediction, medical imaging, diet & exercise plans, and more.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={cn("min-h-screen antialiased")}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  )
}