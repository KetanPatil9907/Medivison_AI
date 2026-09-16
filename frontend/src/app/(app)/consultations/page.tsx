"use client"

import { useState } from "react"
import { CalendarPlus, FileText, Stethoscope, Users } from "lucide-react"

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
import { formatDate } from "@/lib/utils"

interface Overview {
  total_consultations: number
  today_consultations: number
  distinct_patients: number
}

interface Prescription {
  id: number
  medicine_name: string
  dosage: string
  frequency: string
  duration_days: number | null
  instructions: string | null
  is_active: boolean
}

interface Consultation {
  id: number
  appointment_id: number
  notes: string | null
  diagnosis: string | null
  clinical_impression: string | null
  symptoms: string | null
  vital_signs: string | null
  recommended_tests: string | null
  follow_up_date: string | null
  follow_up_instructions: string | null
  status: string
  completed_at: string | null
  created_at: string | null
  patient: { id: number; full_name: string } | null
  appointment: { id: number; scheduled_date: string | null; start_time: string | null; status: string | null } | null
  prescriptions?: Prescription[]
}

interface AppointmentRef {
  id: number
  scheduled_date: string
  start_time: string
  status: string
  patient: { id: number; full_name: string } | null
}

export default function ConsultationsPage() {
  const { data: overview } = useApi<Overview>("/consultations/doctor-overview")
  const { data: list, loading, error, refetch } = useApi<PaginatedData<Consultation>>("/consultations/my?page_size=50")
  const { data: appts } = useApi<PaginatedData<AppointmentRef>>("/appointments/my?page_size=100")
  const [saving, setSaving] = useState(false)
  const [prescribing, setPrescribing] = useState<number | null>(null)
  const [presave, setPresave] = useState(false)

  const stats = [
    { label: "Total consultations", value: overview?.total_consultations ?? "—", icon: Stethoscope },
    { label: "Today", value: overview?.today_consultations ?? "—", icon: CalendarPlus },
    { label: "Distinct patients", value: overview?.distinct_patients ?? "—", icon: Users },
  ]

  const startable = (appts?.items ?? []).filter((a) => ["CONFIRMED", "CHECKED_IN"].includes(a.status))

  async function startConsultation(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setSaving(true)
    try {
      await mutate("/consultations", {
        method: "POST",
        body: {
          appointment_id: Number(fd.get("appointment_id")),
          notes: fd.get("notes") || null,
          diagnosis: fd.get("diagnosis") || null,
          clinical_impression: fd.get("clinical_impression") || null,
          symptoms: fd.get("symptoms") || null,
          vital_signs: fd.get("vital_signs") || null,
          recommended_tests: fd.get("recommended_tests") || null,
          follow_up_instructions: fd.get("follow_up_instructions") || null,
        },
      })
      toast.success("Consultation recorded")
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save consultation")
    } finally {
      setSaving(false)
    }
  }

  async function addPrescription(cid: number, e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setPresave(true)
    try {
      await mutate(`/consultations/${cid}/prescriptions`, {
        method: "POST",
        body: {
          medicine_name: fd.get("medicine_name"),
          dosage: fd.get("dosage"),
          frequency: fd.get("frequency"),
          duration_days: fd.get("duration_days") ? Number(fd.get("duration_days")) : null,
          instructions: fd.get("instructions") || null,
        },
      })
      toast.success("Prescription added")
      setPrescribing(null)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add prescription")
    } finally {
      setPresave(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Consultations"
        description="Record and manage your patient consultations"
        actions={
          <Dialog>
            <DialogTrigger asChild>
              <Button><Stethoscope className="h-4 w-4" /> Start consultation</Button>
            </DialogTrigger>
            <DialogContent className="max-h-[85vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Record a consultation</DialogTitle>
                <DialogDescription>Attach it to a confirmed appointment.</DialogDescription>
              </DialogHeader>
              <form onSubmit={startConsultation} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="cs-appt">Appointment</Label>
                  <Select id="cs-appt" name="appointment_id" required>
                    <option value="">Select…</option>
                    {startable.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.patient?.full_name ?? "Patient"} · {formatDate(a.scheduled_date)} {a.start_time}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <CAField name="symptoms" label="Symptoms reported" text />
                  <CAField name="vital_signs" label="Vital signs" text />
                </div>
                <CAField name="diagnosis" label="Diagnosis" text />
                <CAField name="clinical_impression" label="Clinical impression" text />
                <CAField name="recommended_tests" label="Recommended tests" text />
                <div className="grid gap-3 sm:grid-cols-2">
                  <CAField name="follow_up_instructions" label="Follow-up instructions" text />
                  <div className="space-y-1.5">
                    <Label htmlFor="cs-fu">Follow-up date</Label>
                    <Input id="cs-fu" name="follow_up_date" type="date" />
                  </div>
                </div>
                <CAField name="notes" label="Notes" text />
                <DialogFooter>
                  <DialogClose asChild><Button variant="outline">Close</Button></DialogClose>
                  <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Record consultation"}</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {error ? <Alert variant="destructive" title="Could not load consultations">{error}</Alert> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardContent className="flex items-center justify-between p-5">
              <div>
                <p className="text-sm text-muted-foreground">{s.label}</p>
                <p className="mt-1 text-2xl font-semibold">{s.value}</p>
              </div>
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <s.icon className="h-4 w-4" />
              </span>
            </CardContent>
          </Card>
        ))}
      </div>

      {loading && !list ? <Spinner className="py-10" /> : null}
      {list && list.items.length === 0 ? <EmptyState title="No consultations yet" /> : null}

      <div className="space-y-4">
        {list?.items.map((c) => (
          <Card key={c.id}>
            <CardContent className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <FileText className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="font-medium">{c.patient?.full_name ?? "Patient"}</p>
                    <p className="text-xs text-muted-foreground">
                      {c.appointment?.scheduled_date ? formatDate(c.appointment.scheduled_date) : ""}
                      {c.appointment?.start_time ? ` at ${c.appointment.start_time}` : ""}
                    </p>
                  </div>
                </div>
                <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
              </div>

              <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                {c.diagnosis ? <p><span className="text-muted-foreground">Diagnosis:</span> {c.diagnosis}</p> : null}
                {c.symptoms ? <p><span className="text-muted-foreground">Symptoms:</span> {c.symptoms}</p> : null}
                {c.vital_signs ? <p><span className="text-muted-foreground">Vitals:</span> {c.vital_signs}</p> : null}
                {c.recommended_tests ? <p><span className="text-muted-foreground">Tests:</span> {c.recommended_tests}</p> : null}
              </div>
              {c.notes ? <p className="mt-2 text-sm text-muted-foreground">{c.notes}</p> : null}

              {c.prescriptions && c.prescriptions.length > 0 ? (
                <div className="mt-3 rounded-lg bg-muted p-3">
                  <p className="text-sm font-medium">Prescriptions</p>
                  <ul className="mt-1 space-y-1 text-sm">
                    {c.prescriptions.map((p) => (
                      <li key={p.id}>
                        {p.medicine_name} — {p.dosage} · {p.frequency}
                        {p.duration_days ? ` · ${p.duration_days} days` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="mt-3 flex gap-2">
                <Dialog open={prescribing === c.id} onOpenChange={(open) => setPrescribing(open ? c.id : null)}>
                  <DialogTrigger asChild>
                    <Button size="sm" variant="outline">Add prescription</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Add prescription</DialogTitle>
                      <DialogDescription>Prescribe a medicine for this consultation.</DialogDescription>
                    </DialogHeader>
                    <form onSubmit={(e) => addPrescription(c.id, e)} className="space-y-3">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <RxField name="medicine_name" label="Medicine" required />
                        <RxField name="dosage" label="Dosage" required />
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <RxField name="frequency" label="Frequency" required placeholder="e.g. once daily after meals" />
                        <RxField name="duration_days" label="Duration (days)" type="number" min={1} />
                      </div>
                      <RxField name="instructions" label="Instructions" />
                      <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Close</Button></DialogClose>
                        <Button type="submit" disabled={presave}>{presave ? "Saving…" : "Add"}</Button>
                      </DialogFooter>
                    </form>
                  </DialogContent>
                </Dialog>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function CAField({ name, label, text }: { name: string; label: string; text?: boolean }) {
  return text ? (
    <div className="space-y-1.5">
      <Label htmlFor={`cs-${name}`}>{label}</Label>
      <Textarea id={`cs-${name}`} name={name} rows={2} />
    </div>
  ) : (
    <div className="space-y-1.5">
      <Label htmlFor={`cs-${name}`}>{label}</Label>
      <Input id={`cs-${name}`} name={name} />
    </div>
  )
}

function RxField({ name, label, type = "text", required, min, placeholder }: { name: string; label: string; type?: string; required?: boolean; min?: number; placeholder?: string }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={`rx-${name}`}>{label}</Label>
      <Input id={`rx-${name}`} name={name} type={type} required={required} min={min} placeholder={placeholder} />
    </div>
  )
}