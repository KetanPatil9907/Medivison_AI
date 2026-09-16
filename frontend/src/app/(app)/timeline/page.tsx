"use client"

import { useState } from "react"
import { Activity, History } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { Select } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { useApi } from "@/hooks/use-api"
import type { PaginatedData } from "@/lib/types"
import { formatDate, titleCase } from "@/lib/utils"

const EVENT_ICON: Record<string, string> = {
  appointment: "📅",
  report: "📄",
  test: "🧪",
  risk_assessment: "📊",
  ai_analysis: "🧠",
  consultation: "🩺",
  prescription: "💊",
  metric: "📈",
  vaccination: "💉",
  health_event: "❤️",
}

interface TimelineEvent {
  id: number
  event_type: string
  title: string
  description: string | null
  event_date: string
  severity: string | null
  metadata_json: unknown | null
  created_at: string | null
}

interface TimelineDay {
  date: string
  events: TimelineEvent[]
}

interface Stats {
  total: number
  stats: { event_type: string; count: number }[]
}

export default function TimelinePage() {
  const [type, setType] = useState("")
  const { data, loading, error } = useApi<PaginatedData<TimelineDay>>(
    `/timeline/my?page_size=100${type ? `&event_type=${type}` : ""}`,
  )
  const { data: stats } = useApi<Stats>("/timeline/stats")

  return (
    <div className="space-y-6">
      <PageHeader
        title="Health timeline"
        description="Every event from your care journey, in one place"
        actions={
          <Select value={type} onChange={(e) => setType(e.target.value)} className="w-44">
            <option value="">All events</option>
            <option value="appointment">Appointments</option>
            <option value="report">Reports</option>
            <option value="test">Tests</option>
            <option value="risk_assessment">Risk assessments</option>
            <option value="ai_analysis">AI analyses</option>
            <option value="consultation">Consultations</option>
            <option value="prescription">Prescriptions</option>
            <option value="metric">Metrics</option>
            <option value="health_event">Health events</option>
          </Select>
        }
      />

      {error ? <Alert variant="destructive" title="Could not load timeline">{error}</Alert> : null}

      <div className="grid gap-6 lg:grid-cols-4">
        <div className="lg:col-span-3">
          {loading && !data ? <Spinner className="py-10" /> : null}
          {data && data.items.length === 0 ? <EmptyState title="Nothing on your timeline yet" /> : null}
          <div className="space-y-6">
            {data?.items.map((day) => (
              <div key={day.date}>
                <p className="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <Activity className="h-4 w-4 text-primary" /> {formatDate(day.date)}
                </p>
                <div className="space-y-2 pl-2">
                  {day.events.map((e) => (
                    <Card key={e.id}>
                      <CardContent className="flex items-start gap-3 p-4">
                        <span className="text-xl leading-none">{EVENT_ICON[e.event_type] ?? "•"}</span>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-medium">{e.title}</p>
                            <Badge variant="outline" className="capitalize">{e.event_type.replaceAll("_", " ")}</Badge>
                            {e.severity ? (
                              <Badge variant={e.severity === "high" ? "danger" : e.severity === "moderate" ? "warning" : "info"}>
                                {titleCase(e.severity)}
                              </Badge>
                            ) : null}
                          </div>
                          {e.description ? <p className="mt-1 text-sm text-muted-foreground">{e.description}</p> : null}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><History className="h-4 w-4" /> Summary</CardTitle>
            </CardHeader>
            <CardContent>
              {!stats ? <Spinner className="py-8" /> : null}
              {stats && stats.total === 0 ? <EmptyState title="No events yet" /> : null}
              {stats && stats.total > 0 ? (
                <ul className="space-y-2">
                  <li className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Total events</span>
                    <span className="font-semibold">{stats.total}</span>
                  </li>
                  {stats.stats.map((s) => (
                    <li key={s.event_type} className="flex justify-between text-sm">
                      <span className="capitalize text-muted-foreground">{s.event_type.replaceAll("_", " ")}</span>
                      <span className="font-medium">{s.count}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}