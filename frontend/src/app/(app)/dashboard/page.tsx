"use client"

import Link from "next/link"
import {
  Activity,
  ArrowRight,
  Brain,
  CalendarDays,
  ClipboardList,
  Dumbbell,
  FileText,
  HeartPulse,
  Pill,
  ScanEye,
  Sparkles,
  Stethoscope,
  UtensilsCrossed,
  Users,
} from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge, statusVariant } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useApi } from "@/hooks/use-api"
import { useAuth } from "@/lib/auth"
import type { AdminDashboardPayload, DashboardPayload, DoctorDashboardPayload, PatientDashboardPayload } from "@/lib/types"
import { formatDate, percentColor, titleCase } from "@/lib/utils"

const QUICK_LINKS: Record<string, { label: string; href: string; icon: typeof Brain; color: string }[]> = {
  PATIENT: [
    { label: "Symptom Checker", href: "/symptoms", icon: Brain, color: "text-violet-600 bg-violet-50" },
    { label: "Risk Assessment", href: "/risk", icon: HeartPulse, color: "text-rose-600 bg-rose-50" },
    { label: "Vision Analysis", href: "/vision", icon: ScanEye, color: "text-sky-600 bg-sky-50" },
    { label: "Diet Plan", href: "/diet", icon: UtensilsCrossed, color: "text-emerald-600 bg-emerald-50" },
    { label: "Exercise Plan", href: "/exercise", icon: Dumbbell, color: "text-amber-600 bg-amber-50" },
    { label: "Book Appointment", href: "/appointments", icon: CalendarDays, color: "text-indigo-600 bg-indigo-50" },
    { label: "Medications", href: "/medications", icon: Pill, color: "text-teal-600 bg-teal-50" },
    { label: "Wellness", href: "/wellness", icon: Sparkles, color: "text-fuchsia-600 bg-fuchsia-50" },
  ],
}

export default function DashboardPage() {
  const { user } = useAuth()
  const { data, loading, error } = useApi<DashboardPayload>("/dashboard")

  if (!user) return null

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back, ${user.full_name.split(" ")[0] ?? "there"}`}
        description={data?.role ? `${titleCase(data.role)} dashboard` : undefined}
      />

      {error ? <Alert variant="destructive" title="Could not load dashboard">{error}</Alert> : null}

      {loading && !data ? <Spinner className="py-16" /> : null}

      {data?.role === "PATIENT" ? <PatientDashboard payload={data} /> : null}
      {data?.role === "DOCTOR" ? <DoctorDashboard payload={data} /> : null}
      {data?.role === "ADMIN" ? <AdminDashboard payload={data} /> : null}
    </div>
  )
}

function StatCard({ label, value, sub, icon: Icon }: { label: string; value: React.ReactNode; sub?: React.ReactNode; icon: typeof Brain }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="mt-1 text-2xl font-semibold">{value === null || value === undefined ? "—" : value}</p>
            {sub ? <p className="mt-0.5 truncate text-xs text-muted-foreground">{sub}</p> : null}
          </div>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-4 w-4" />
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

function PatientDashboard({ payload }: { payload: PatientDashboardPayload }) {
  const cards = payload.overview_cards
  const score = payload.health_score.score
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Upcoming appointments" value={cards.upcoming_appointments} icon={CalendarDays} />
        <StatCard label="Completed appointments" value={cards.completed_appointments} icon={ClipboardList} />
        <StatCard label="Active medications" value={cards.active_medications} icon={Pill} />
        <StatCard
          label="Health score"
          value={score === null ? "—" : score}
          sub={score === null ? undefined : `Last measured ${formatDate(payload.health_score.recorded_date)}`}
          icon={Activity}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Next appointment</CardTitle>
            <CardDescription>Your closest scheduled visit</CardDescription>
          </CardHeader>
          <CardContent>
            {payload.upcoming_appointment ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium">{payload.upcoming_appointment.doctor_full_name ?? "Doctor"}</p>
                  <Badge variant={statusVariant(payload.upcoming_appointment.status)}>{payload.upcoming_appointment.status}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {payload.upcoming_appointment.specialization ?? "General"} ·{" "}
                  {formatDate(payload.upcoming_appointment.date)} at {payload.upcoming_appointment.start_time}
                </p>
                {payload.upcoming_appointment.hospital ? (
                  <p className="text-sm text-muted-foreground">{payload.upcoming_appointment.hospital}</p>
                ) : null}
                <Button asChild variant="outline" className="mt-2">
                  <Link href="/appointments">
                    Manage appointments <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            ) : (
              <EmptyState title="No upcoming appointments" description="Book an appointment with a doctor." />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI insights</CardTitle>
            <CardDescription>Latest risk and vision results</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {payload.ai_insights.risk_assessment ? (
              <div className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <p className="text-sm font-medium">{titleCase(payload.ai_insights.risk_assessment.condition_type)} risk</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(payload.ai_insights.risk_assessment.recorded_date)} · {titleCase(payload.ai_insights.risk_assessment.risk_level)}
                  </p>
                </div>
                <span className={`text-lg font-semibold ${percentColor(payload.ai_insights.risk_assessment.risk_percentage)}`}>
                  {payload.ai_insights.risk_assessment.risk_percentage}%
                </span>
              </div>
            ) : (
              <Alert variant="default">
                No risk assessment yet —{" "}
                <Link href="/risk" className="font-medium underline">
                  run one now
                </Link>
                .
              </Alert>
            )}
            {payload.ai_insights.image_analysis ? (
              <div className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <p className="text-sm font-medium">{titleCase(payload.ai_insights.image_analysis.modality)}</p>
                  <p className="text-xs text-muted-foreground">{formatDate(payload.ai_insights.image_analysis.recorded_date)}</p>
                </div>
                <span className="text-right">
                  <span className="block text-sm font-medium">{payload.ai_insights.image_analysis.prediction_label}</span>
                  <span className="text-xs text-muted-foreground">{(payload.ai_insights.image_analysis.confidence * 100).toFixed(1)}%</span>
                </span>
              </div>
            ) : (
              <Alert variant="default">
                No vision analyses yet —{" "}
                <Link href="/vision" className="font-medium underline">
                  try one
                </Link>
                .
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>From your health timeline</CardDescription>
          </CardHeader>
          <CardContent>
            {payload.recent_timeline.length === 0 ? (
              <EmptyState title="No timeline events yet" />
            ) : (
              <ul className="divide-y">
                {payload.recent_timeline.map((t, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 py-2.5">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{t.title}</p>
                      <p className="text-xs text-muted-foreground">{formatDate(t.event_date)}</p>
                    </div>
                    {t.severity ? <Badge variant="info">{titleCase(t.severity)}</Badge> : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick actions</CardTitle>
            <CardDescription>Jump straight into your care tools</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              {QUICK_LINKS.PATIENT.map(({ label, href, icon: Icon, color }) => (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                >
                  <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${color}`}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="text-sm font-medium">{label}</span>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <TrendsCard trends={payload.trends} />
    </div>
  )
}

function TrendsCard({ trends }: { trends: PatientDashboardPayload["trends"] }) {
  const names = Object.keys(trends)
  if (names.length === 0) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>Health metric trends</CardTitle>
        <CardDescription>Last 30 days</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        {names.map((name) => {
          const series = trends[name]
          if (!series || series.values.length === 0) return null
          const latest = series.values[series.values.length - 1]
          const first = series.values[0]
          const delta = latest - first
          return (
            <div key={name} className="rounded-lg border p-4">
              <div className="flex items-baseline justify-between">
                <p className="text-sm font-medium">{titleCase(name)}</p>
                <div className="text-right">
                  <p className="text-lg font-semibold">{typeof latest === "number" ? latest.toFixed(1) : latest}</p>
                  <p className={`text-xs ${delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                    {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)} in 30d
                  </p>
                </div>
              </div>
              <svg viewBox="0 0 200 40" preserveAspectRatio="none" className="mt-2 h-10 w-full">
                <path
                  d={sparkPath(series.values)}
                  fill="none"
                  stroke="hsl(199 89% 48%)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

function sparkPath(values: number[]): string {
  if (values.length < 2) return ""
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * 200
      const y = 38 - ((v - min) / span) * 32
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(" ")
}

function DoctorDashboard({ payload }: { payload: DoctorDashboardPayload }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total patients" value={payload.stats.total_patients} icon={Users} />
        <StatCard label="Completed consultations" value={payload.stats.completed_consultations} icon={Stethoscope} />
        <StatCard label="Upcoming appointments" value={payload.stats.upcoming} icon={CalendarDays} />
        <StatCard label="Pending requests" value={payload.stats.pending_requests} icon={ClipboardList} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s schedule</CardTitle>
          <CardDescription>Patients seen today</CardDescription>
        </CardHeader>
        <CardContent>
          {payload.today_schedule.length === 0 ? (
            <EmptyState title="No appointments today" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Patient</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Queue</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {payload.today_schedule.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>
                      {a.start_time}–{a.end_time}
                    </TableCell>
                    <TableCell className="font-medium">{a.patient_full_name ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(a.status)}>{a.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">{a.queue_position ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Upcoming appointments</CardTitle>
          </CardHeader>
          <CardContent>
            {payload.upcoming_appointments.length === 0 ? (
              <EmptyState title="No upcoming" />
            ) : (
              <ul className="divide-y">
                {payload.upcoming_appointments.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-2 py-2.5">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{a.patient_full_name ?? "Patient"}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(a.scheduled_date)} · {a.start_time}–{a.end_time} · {titleCase(a.consultation_type)}
                      </p>
                    </div>
                    <Badge variant={statusVariant(a.status)}>{a.status}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent consultations</CardTitle>
          </CardHeader>
          <CardContent>
            {payload.recent_activity.length === 0 ? (
              <EmptyState title="No consultations yet" />
            ) : (
              <ul className="divide-y">
                {payload.recent_activity.map((c) => (
                  <li key={c.id} className="py-2.5">
                    <p className="text-sm font-medium">{c.title}</p>
                    {c.description ? <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{c.description}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function AdminDashboard({ payload }: { payload: AdminDashboardPayload }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total patients" value={payload.stats.total_patients} icon={Users} />
        <StatCard label="Total doctors" value={payload.stats.total_doctors} icon={Stethoscope} />
        <StatCard
          label="Pending applications"
          value={payload.stats.pending_applications}
          icon={ClipboardList}
          sub={
            payload.stats.pending_applications > 0 ? (
              <Link href="/admin/applications" className="underline">
                Review now
              </Link>
            ) : undefined
          }
        />
        <StatCard label="Active doctors" value={payload.stats.approved_doctors} icon={Users} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Member growth</CardTitle>
            <CardDescription>Last 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            <svg viewBox="0 0 400 140" className="h-36 w-full">
              <GrowthAreaChart data={payload.user_growth} />
            </svg>
            <div className="mt-2 flex items-center justify-center gap-6 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-sky-500" /> Patients
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500" /> Doctors
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pending doctor applications</CardTitle>
          </CardHeader>
          <CardContent>
            {payload.pending_applications.length === 0 ? (
              <EmptyState title="Nothing to review" description="All applications have been actioned." />
            ) : (
              <ul className="divide-y">
                {payload.pending_applications.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-2 py-2.5">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{a.full_name ?? "Applicant"}</p>
                      <p className="text-xs text-muted-foreground">
                        {a.specialization} · submitted {formatDate(a.submitted_at)}
                      </p>
                    </div>
                    <Button asChild size="sm" variant="outline">
                      <Link href="/admin/applications">Review</Link>
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function GrowthAreaChart({ data }: { data: AdminDashboardPayload["user_growth"] }) {
  const n = Math.max(2, data.length)
  const w = 400
  const h = 140
  const pad = 6
  const step = (w - pad * 2) / (n - 1)

  const line = (values: number[], color: string) => {
    if (values.length === 0) return null
    const max = Math.max(1, ...values)
    const pts = values
      .map((v, i) => {
        const x = pad + i * step
        const y = h - pad - (v / max) * (h - pad * 2)
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(" ")
    const area =
      `${pts} ` +
      `L${(pad + (values.length - 1) * step).toFixed(1)},${(h - pad).toFixed(1)} ` +
      `L${pad.toFixed(1)},${(h - pad).toFixed(1)} Z`
    const labelFilter = Math.ceil(n / 6)
    return (
      <>
        <path d={area} fill={color} opacity="0.15" />
        <path d={pts} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        {data
          .filter((_, i) => i % Math.max(1, labelFilter) === 0)
          .map((d) => (
            <text key={d.date} x={pad + data.indexOf(d) * step} y={h - 3} textAnchor="middle" fontSize="8" fill="hsl(199 12% 45%)">
              {d.date.slice(5)}
            </text>
          ))}
      </>
    )
  }

  return (
    <>
      {line(data.map((d) => d.patients), "#0ea5e9")}
      {line(data.map((d) => d.doctors), "#10b981")}
    </>
  )
}