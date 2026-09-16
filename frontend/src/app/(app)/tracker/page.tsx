"use client"

import { useState } from "react"
import { Activity, LineChart, UserPlus } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageHeader } from "@/components/ui/page-header"
import { Select } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"
import { formatDate, titleCase } from "@/lib/utils"

const METRIC_TYPES = ["weight", "bp", "blood_sugar", "heart_rate", "sleep", "activity", "bmi", "water_intake"]

const UNIT_HINT: Record<string, string> = {
  weight: "kg",
  bp: "mmHg",
  blood_sugar: "mg/dL",
  heart_rate: "bpm",
  sleep: "hours",
  activity: "steps",
  water_intake: "mL",
}

interface Metric {
  id: number
  metric_type: string
  value: number
  unit: string | null
  systolic: number | null
  diastolic: number | null
  recorded_date: string
  notes: string | null
}

interface FamilyProfile {
  id: number
  name: string
  relationship: string
  age: number | null
  blood_group: string | null
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

export default function TrackerPage() {
  const { data, loading, error, refetch } = useApi<Metric[]>("/patients/me/health-metrics")
  const { data: family, refetch: refetchFamily } = useApi<FamilyProfile[]>("/patients/me/family-profiles")

  const [metricType, setMetricType] = useState("weight")
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const isBp = metricType === "bp"
  const unit = UNIT_HINT[metricType] ?? ""

  async function addMetric(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setSaving(true)
    try {
      await mutate("/patients/me/health-metrics", {
        method: "POST",
        body: {
          metric_type: metricType,
          value: Number(fd.get("value")),
          unit: unit || (fd.get("unit") as string) || null,
          systolic: isBp ? Number(fd.get("systolic")) || null : null,
          diastolic: isBp ? Number(fd.get("diastolic")) || null : null,
          recorded_date: fd.get("recorded_date") || todayStr(),
          notes: fd.get("notes") || null,
        },
      })
      toast.success("Measurement saved")
      setOpen(false)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save measurement")
    } finally {
      setSaving(false)
    }
  }

  async function remove(id: number) {
    if (!confirm("Delete this measurement?")) return
    try {
      await mutate(`/patients/me/health-metrics/${id}`, { method: "DELETE" })
      toast.success("Measurement deleted")
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed")
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Health tracker"
        description="Log and review your daily health metrics"
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button><Activity className="h-4 w-4" /> Add measurement</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add measurement</DialogTitle>
                <DialogDescription>Record a new health metric.</DialogDescription>
              </DialogHeader>
              <form onSubmit={addMetric} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="metric-type">Metric</Label>
                  <Select id="metric-type" value={metricType} onChange={(e) => setMetricType(e.target.value)}>
                    {METRIC_TYPES.map((m) => (
                      <option key={m} value={m}>{titleCase(m)}</option>
                    ))}
                  </Select>
                </div>
                {isBp ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label htmlFor="bp-sys">Systolic</Label>
                      <Input id="bp-sys" name="systolic" type="number" required placeholder="120" />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="bp-dia">Diastolic</Label>
                      <Input id="bp-dia" name="diastolic" type="number" required placeholder="80" />
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <Label htmlFor="metric-value">Value{unit ? ` (${unit})` : ""}</Label>
                    <Input id="metric-value" name="value" type="number" step="any" required />
                  </div>
                )}
                <div className="space-y-1.5">
                  <Label htmlFor="metric-date">Date</Label>
                  <Input id="metric-date" name="recorded_date" type="date" defaultValue={todayStr()} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="metric-notes">Notes (optional)</Label>
                  <Input id="metric-notes" name="notes" placeholder="e.g. after morning walk" />
                </div>
                <DialogFooter>
                  <DialogClose asChild><Button variant="outline">Close</Button></DialogClose>
                  <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Save measurement"}</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {error ? <Alert variant="destructive" title="Could not load metrics">{error}</Alert> : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><LineChart className="h-4 w-4" /> Latest measurements</CardTitle>
            <CardDescription>Your most recent values per metric</CardDescription>
          </CardHeader>
          <CardContent>
            {loading && !data ? <Spinner className="py-10" /> : null}
            {data && data.length === 0 ? <EmptyState title="No measurements yet" /> : null}
            {data && data.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {METRIC_TYPES.map((type) => {
                  const items = (data ?? []).filter((m) => m.metric_type === type).slice(0, 3)
                  if (items.length === 0) return null
                  const latest = items[0]
                  return (
                    <div key={type} className="rounded-lg border p-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium">{titleCase(type)}</p>
                        <Badge variant="outline">{items.length} records</Badge>
                      </div>
                      <p className="mt-1 text-xl font-semibold">
                        {latest.metric_type === "bp"
                          ? `${latest.systolic}/${latest.diastolic}`
                          : `${latest.value}${latest.unit ? ` ${latest.unit}` : ""}`}
                      </p>
                      <p className="text-xs text-muted-foreground">Last {formatDate(latest.recorded_date)}</p>
                    </div>
                  )
                })}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Family profiles</CardTitle>
            <CardDescription>Track care for loved ones</CardDescription>
          </CardHeader>
          <CardContent>
            {family && family.length === 0 ? <EmptyState title="No family profiles" /> : null}
            {family && family.length > 0 ? (
              <ul className="divide-y">
                {family.map((f) => (
                  <li key={f.id} className="py-2.5">
                    <p className="text-sm font-medium">{f.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {titleCase(f.relationship)} · {f.age ? `${f.age} yrs` : "—"} {f.blood_group ? `· ${f.blood_group}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}