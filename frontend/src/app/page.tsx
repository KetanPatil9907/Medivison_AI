import Link from "next/link"

import { Button } from "@/components/ui/button"
import {
  Activity,
  Brain,
  Eye,
  HeartPulse,
  Stethoscope,
  Utensils,
  UserPlus,
  LogIn,
  MessageSquareHeart,
} from "lucide-react"

const features = [
  {
    icon: Brain,
    title: "AI Symptom Checker",
    description: "Analyze symptoms and get triage guidance with urgency flags.",
  },
  {
    icon: HeartPulse,
    title: "Health Risk Prediction",
    description: "Estimates for diabetes, hypertension, heart disease and more.",
  },
  {
    icon: Eye,
    title: "Medical Vision",
    description: "Upload imaging studies for AI-assisted analysis with heatmaps.",
  },
  {
    icon: Utensils,
    title: "Diet & Exercise Plans",
    description: "Personalized daily meal plans and weekly workout schedules.",
  },
  {
    icon: MessageSquareHeart,
    title: "AI Health Assistant",
    description: "Chat for quick answers, lifestyle guidance and emergency detection.",
  },
  {
    icon: Stethoscope,
    title: "Care Management",
    description: "Appointments, records, medications, reports and family profiles.",
  },
]

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-sky-50 to-white text-slate-900">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2 font-semibold">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Activity className="h-5 w-5" />
          </span>
          MediVision AI
        </div>
        <nav className="flex items-center gap-2">
          <Button asChild variant="ghost">
            <Link href="/login">
              <LogIn className="h-4 w-4" /> Log in
            </Link>
          </Button>
          <Button asChild>
            <Link href="/register">
              <UserPlus className="h-4 w-4" /> Get started
            </Link>
          </Button>
        </nav>
      </header>

      <section className="mx-auto max-w-6xl px-6 pb-16 pt-12 text-center">
        <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
          Your AI-powered healthcare companion
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600">
          MediVision combines AI health tools with real care workflows — symptoms, risk, vision,
          nutrition, exercise and consultations — all in one secure platform.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button asChild size="lg">
            <Link href="/register">Create free account</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/login">Sign in to your dashboard</Link>
          </Button>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-6 pb-24 sm:grid-cols-2 lg:grid-cols-3">
        {features.map(({ icon: Icon, title, description }) => (
          <div
            key={title}
            className="rounded-2xl border border-slate-200 bg-white/70 p-6 shadow-sm backdrop-blur"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-100 text-sky-700">
              <Icon className="h-5 w-5" />
            </span>
            <h2 className="mt-4 font-semibold">{title}</h2>
            <p className="mt-1 text-sm text-slate-600">{description}</p>
          </div>
        ))}
      </section>

      <footer className="border-t border-slate-200 py-6 text-center text-sm text-slate-500">
        MediVision AI — demo healthcare platform. Not a substitute for professional medical advice.
      </footer>
    </main>
  )
}