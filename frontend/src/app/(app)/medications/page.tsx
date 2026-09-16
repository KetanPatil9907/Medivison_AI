"use client"

import { useState } from "react"
import { Bell, CheckCircle2, Clock, Pill, Plus } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge, statusVariant } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageHeader } from "@/components/ui/page-header"
import { Select } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"
import type { PaginatedData } from "@/lib/types"

const FREQUENCIES = ["once_daily", "twice_daily", "thrice_daily", "every_other_day", "weekly", "as_needed", "custom"]

interface Medication {
  id: number
  name: string
  dosage: string
  frequency: string
  frequency_detail: string | null
  times_per_day: number
  start_date: string | null
  end_date: string | null
  reminder_enabled: boolean
  instructions: string | null
  prescribed_by: string | null
  status: string
  adherence_rate: number | null
  created_at: string | null
}

interface Reminder {
  id: number
  name: string
  dosage: string
  frequency: string
  frequency_detail: string | null
  times_per_day: number
  instructions: string | null
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

export default function MedicationsPage() {
  const { data, loading, error, refetch } = useApi<PaginatedData<Medication>>("/medications/my?page_size=100")
  const { data: reminders } = useApi<Reminder[]>("/medications/reminders/today")

  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  async function addMedication(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setSaving(true)
    try {
      await mutate("/medications", {
        method: "POST",
        body: {
          name: fd.get("name"),
          dosage: fd.get("dosage"),
          frequency: fd.get("frequency"),
          frequency_detail: fd.get("frequency_detail") || null,
          times_per_day: Number(fd.get("times_per_day") || 1),
          start_date: fd.get("start_date") || todayStr(),
          end_date: fd.get("end_date") || null,
          reminder_enabled: fd.get("reminder_enabled") === "on",
          instructions: fd.get("instructions") || null,
          prescribed_by: fd.get("prescribed_by") || null,
        },
      })
      toast.success("Medication added")
      setOpen(false)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add medication")
    } finally {
      setSaving(false)
    }
  }

  async function setStatus(id: number, status: string) {
    try {
      await mutate(`/medications/${id}/status`, { method: "PATCH", body: { status } })
      toast.success(`Marked ${status}`)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed")
    }
  }

  async function logIntake(id: number, taken: boolean) {
    try {
      await mutate(`/medications/${id}/log`, { method: "POST", body: { taken } })
      toast.success(taken ? "Dose logged as taken" : "Dose skipped")
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not log dose")
    }
  }

  const reminderList = Array.isArray(reminders) ? reminders : []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Medications"
        description="Track your prescriptions and daily doses"
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4" /> Add medication
              </Button>
            </DialogTrigger>
            <DialogContent className="max-h-[85vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Add medication</DialogTitle>
                <DialogDescription>Add a prescription to your daily plan.</DialogDescription>
              </DialogHeader>
              <form onSubmit={addMedication} className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field name="name" label="Medication name" required />
                  <Field name="dosage" label="Dosage" placeholder="e.g. 500 mg, 2 puffs" required />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="freq">Frequency</Label>
                    <Select id="freq" name="frequency" defaultValue="once_daily" required>
                      {FREQUENCIES.map((f) => (
                        <option key={f} value={f}>{f.replaceAll("_", " ")}</option>
                      ))}
                    </Select>
                  </div>
                  <Field name="times_per_day" label="Times per day" type="number" min={1} max={24} defaultValue="1" />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field name="start_date" label="Start date" type="date" defaultValue={todayStr()} />
                  <Field name="end_date" label="End date (optional)" type="date" />
                </div>
                <Field name="frequency_detail" label="Frequency detail (optional)" placeholder="e.g. morning and night" />
                <Field name="prescribed_by" label="Prescribed by (optional)" />
                <div className="space-y-1.5">
                  <Label htmlFor="instr">Instructions</Label>
                  <Textarea id="instr" name="instructions" rows={2} placeholder="e.g. take with food" />
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="reminder_enabled" defaultChecked className="h-4 w-4 rounded border-border" />
                  Enable dose reminders
                </label>
                <DialogFooter>
                  <DialogClose asChild><Button type="button" variant="outline">Close</Button></DialogClose>
                  <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Add medication"}</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {error ? <Alert variant="destructive" title="Could not load medications">{error}</Alert> : null}

      {reminderList.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-4 w-4" /> Today&apos;s doses
            </CardTitle>
            <CardDescription>Tap to log each dose</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {reminderList.map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-2 rounded-lg border p-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{r.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {r.dosage} · {r.frequency.replaceAll("_", " ")}
                    </p>
                  </div>
                  <Button size="sm" onClick={() => logIntake(r.id, true)}>
                    <CheckCircle2 className="h-4 w-4" /> Log taken
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {loading && !data ? <Spinner className="py-10" /> : null}
      {data && data.items.length === 0 ? (
        <EmptyState title="No medications yet" description="Add your first medication to start tracking." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data?.items.map((m) => (
            <Card key={m.id}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Pill className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="font-medium">{m.name}</p>
                      <p className="text-xs text-muted-foreground">{m.dosage}</p>
                    </div>
                  </div>
                  <Badge variant={statusVariant(m.status)}>{m.status}</Badge>
                </div>
                <div className="mt-4 space-y-1 text-sm text-muted-foreground">
                  <p className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" /> {m.frequency.replaceAll("_", " ")}
                    {m.frequency_detail ? ` — ${m.frequency_detail}` : ""}
                  </p>
                  <p>Started {m.start_date ?? "—"}{m.end_date ? ` · until ${m.end_date}` : ""}</p>
                  {m.prescribed_by ? <p>Prescribed by {m.prescribed_by}</p> : null}
                  {m.adherence_rate !== null ? <p>Adherence: {m.adherence_rate}%</p> : null}
                </div>
                {m.instructions ? <p className="mt-3 text-sm text-muted-foreground">{m.instructions}</p> : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => logIntake(m.id, true)}>Log taken</Button>
                  {m.status === "active" ? (
                    <Button size="sm" variant="outline" onClick={() => setStatus(m.id, "paused")}>Pause</Button>
                  ) : (
                    <Button size="sm" variant="outline" onClick={() => setStatus(m.id, "active")}>Resume</Button>
                  )}
                  <Button size="sm" variant="outline" className="text-rose-600" onClick={() => setStatus(m.id, "discontinued")}>
                    Stop
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function Field({
  name,
  label,
  type = "text",
  required,
  placeholder,
  min,
  max,
  defaultValue,
}: {
  name: string
  label: string
  type?: string
  required?: boolean
  placeholder?: string
  min?: number
  max?: number
  defaultValue?: string
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={`med-${name}`}>{label}</Label>
      <Input id={`med-${name}`} name={name} type={type} required={required} placeholder={placeholder} min={min} max={max} defaultValue={defaultValue} />
    </div>
  )
}