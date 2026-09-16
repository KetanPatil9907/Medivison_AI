"use client"

import { Activity, Brain, CalendarHeart, LineChart, ScanEye, Sigma, Users, Stethoscope, FileCheck2 } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { Spinner } from "@/components/ui/spinner"
import { useApi } from "@/hooks/use-api"

interface PlatformAnalytics {
  total_patients: number
  total_doctors: number
  total_appointments: number
  completed_consultations: number
  ai_usage: {
    symptom_checks: number
    risk_assessments: number
    image_analyses: number
  }
  snapshot_id: number
  disclaimer: string
}

export default function AdminAnalyticsPage() {
  const { data, loading, error } = useApi<PlatformAnalytics>("/analytics/platform")

  const ai = data?.ai_usage ?? { symptom_checks: 0, risk_assessments: 0, image_analyses: 0 }
  const totalAi = ai.symptom_checks + ai.risk_assessments + ai.image_analyses
  const maxAi = Math.max(ai.symptom_checks, ai.risk_assessments, ai.image_analyses, 1)

  const cards = [
    { label: "Patients", value: data?.total_patients, icon: Users },
    { label: "Doctors", value: data?.total_doctors, icon: Stethoscope },
    { label: "Appointments", value: data?.total_appointments, icon: CalendarHeart },
    { label: "Completed consultations", value: data?.completed_consultations, icon: FileCheck2 },
  ]

  const aiBars = [
    { label: "Symptom checks", key: "symptom_checks" as const, icon: Brain },
    { label: "Risk assessments", key: "risk_assessments" as const, icon: Activity },
    { label: "Image analyses", key: "image_analyses" as const, icon: ScanEye },
  ]

  return (
    <div className="space-y-6">
      <PageHeader title="Platform analytics" description="Usage snapshot of the MediVision platform" />

      {error ? <Alert variant="destructive" title="Could not load analytics">{error}</Alert> : null}
      {loading && !data ? <Spinner className="py-10" /> : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((c) => (
          <Card key={c.label}>
            <CardContent className="flex items-center justify-between p-5">
              <div>
                <p className="text-sm text-muted-foreground">{c.label}</p>
                <p className="mt-1 text-2xl font-semibold">{c.value ?? "—"}</p>
              </div>
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <c.icon className="h-5 w-5" />
              </span>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Brain className="h-4 w-4 text-primary" /> AI usage <span className="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">{totalAi}</span></CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {totalAi === 0 ? <p className="text-sm text-muted-foreground">No AI features used yet.</p> : null}
            {aiBars.map((b) => (
              <div key={b.key}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="flex items-center gap-1.5"><b.icon className="h-4 w-4 text-muted-foreground" /> {b.label}</span>
                  <span className="font-medium">{ai[b.key]}</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${(ai[b.key] / maxAi) * 100}%` }}
                  />
                </div>
              </div>
            ))}
            {data?.disclaimer ? <p className="border-t pt-3 text-xs text-muted-foreground">{data.disclaimer}</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><LineChart className="h-4 w-4 text-primary" /> Adoption <Sigma className="h-4 w-4 text-primary" /></CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-2">
              <Stat label="Patience visits" hint="patients" value={0} hidden={true} />
            </div>
            <SvgRing value={(data?.total_appointments ?? 0) + (data?.completed_consultations ?? 0)} max={Math.max((data?.total_appointments ?? 0) * 2, 1)} />
            <div className="mt-4 space-y-3 text-sm">
              <RatioRow label="Consultations / appointments" a={data?.completed_consultations ?? 0} b={data?.total_appointments ?? 0} />
              <RatioRow label="Patients per doctor" a={data?.total_patients ?? 0} b={Math.max(data?.total_doctors ?? 0, 1)} decimals={1} />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function Stat({ label, value, hint, hidden }: { label: string; value: number; hint: string; hidden?: boolean }) {
  if (hidden) return null
  return (
    <div className="flex justify-between rounded-lg bg-muted p-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold">{value} <span className="font-normal text-muted-foreground">{hint}</span></span>
    </div>
  )
}

function SvgRing({ value, max }: { value: number; max: number }) {
  const pct = Math.min(value / max, 1)
  const r = 44
  const c = 2 * Math.PI * r
  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 100 100" className="h-24 w-24">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--color-muted, #e5e7eb)" strokeWidth="10" />
        <circle
          cx="50"
          cy="50"
          r={r}
          fill="none"
          stroke="var(--color-primary, #2563eb)"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          transform="rotate(-90 50 50)"
        />
        <text x="50" y="52" textAnchor="middle" fontSize="12" fontWeight="600">{(pct * 100).toFixed(0)}%</text>
      </svg>
      <p className="text-sm text-muted-foreground">Engagement: share of appointments that became completed consultations.</p>
    </div>
  )
}

function RatioRow({ label, a, b, decimals = 0 }: { label: string; a: number; b: number; decimals?: number }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{(a / b).toFixed(decimals)}</span>
    </div>
  )
}