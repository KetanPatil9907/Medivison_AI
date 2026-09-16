"use client"

import { useState } from "react"
import { Clock, Plus, Save, Trash2 } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageHeader } from "@/components/ui/page-header"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"
import { titleCase } from "@/lib/utils"

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

interface Slot {
  id?: number
  day_of_week: number
  start_time: string
  end_time: string
  is_blocked?: boolean
}

type EditableSlot = { key: string; id?: number; day_of_week: number; start_time: string; end_time: string; is_blocked?: boolean }

interface DoctorSelf {
  full_name: string
  specialization: string
  qualification: string
  medical_registration_number: string
  years_of_experience: number | null
  hospital: string | null
  clinic_name: string | null
  address: string | null
  consultation_type: string | null
  languages: string | null
  consultation_fee: number | null
  bio: string | null
  online_consultation_enabled: boolean | null
  rating: number | null
}

export default function AvailabilityPage() {
  const { data: slots, loading, error, refetch } = useApi<Slot[]>("/doctors/me/availability")
  const { data: me } = useApi<DoctorSelf>("/doctors/me")
  const [edits, setEdits] = useState<EditableSlot[] | null>(null)
  const [saving, setSaving] = useState(false)

  const schedule: EditableSlot[] = edits ?? (slots ?? []).map((s) => ({ ...s, key: `slot-${s.id}` }))
  const dirty = edits !== null

  function addDraft(day = 0) {
    setEdits((prev) => {
      const base = prev ?? (slots ?? []).map((s) => ({ ...s, key: `slot-${s.id}` }))
      return [...base, { key: crypto.randomUUID(), day_of_week: day, start_time: "09:00", end_time: "10:00" }]
    })
  }

  function updateSlot(key: string, patch: Partial<EditableSlot>) {
    setEdits((prev) => (prev ?? (slots ?? []).map((s) => ({ ...s, key: `slot-${s.id}` }))).map((s) => (s.key === key ? { ...s, ...patch } : s)))
  }

  function removeSlot(key: string) {
    setEdits((prev) => (prev ?? (slots ?? []).map((s) => ({ ...s, key: `slot-${s.id}` }))).filter((s) => s.key !== key))
  }

  async function saveAvailability() {
    const scheduleBody: Slot[] = schedule
      .filter((s) => !s.is_blocked)
      .map((s) => ({ day_of_week: s.day_of_week, start_time: s.start_time, end_time: s.end_time, is_blocked: false }))
    setSaving(true)
    try {
      await mutate("/doctors/me/availability", { method: "PUT", body: { slots: scheduleBody } })
      toast.success("Availability saved")
      setEdits(null)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save availability")
    } finally {
      setSaving(false)
    }
  }

  async function saveProfile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setSaving(true)
    try {
      await mutate("/doctors/me/profile", {
        method: "PUT",
        body: {
          specialization: fd.get("specialization") || null,
          qualification: fd.get("qualification") || null,
          medical_registration_number: fd.get("medical_registration_number") || null,
          years_of_experience: fd.get("years_of_experience") ? Number(fd.get("years_of_experience")) || null : null,
          hospital: fd.get("hospital") || null,
          clinic_name: fd.get("clinic_name") || null,
          address: fd.get("address") || null,
          consultation_type: fd.get("consultation_type") || null,
          languages: fd.get("languages") || null,
          consultation_fee: fd.get("consultation_fee") ? Number(fd.get("consultation_fee")) || null : null,
          bio: fd.get("bio") || null,
          online_consultation_enabled: fd.get("online_consultation_enabled") === "on",
        },
      })
      toast.success("Profile saved")
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save profile")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Availability"
        description="Set your weekly consultation hours"
        actions={
          <Button onClick={saveAvailability} disabled={saving || !dirty}>
            <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save schedule"}
          </Button>
        }
      />

      {error ? <Alert variant="destructive" title="Could not load availability">{error}</Alert> : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Clock className="h-4 w-4" /> Weekly schedule</CardTitle>
            <CardDescription>Save replaces your entire schedule.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading && !slots ? <Spinner className="py-10" /> : null}
            <div className="space-y-5">
              {DAYS.map((day, i) => {
                const daySlots = schedule.filter((s) => s.day_of_week === i)
                return (
                  <div key={day} className="grid gap-2 sm:grid-cols-[150px_1fr]">
                    <p className="pt-2 text-sm font-medium">{day}</p>
                    <div className="space-y-2">
                      {daySlots.length === 0 ? <p className="text-sm text-muted-foreground">No slots</p> : null}
                      {daySlots.map((s) => (
                        <div key={s.key} className="flex items-center gap-2">
                          <Input
                            type="time"
                            value={s.start_time}
                            onChange={(e) => updateSlot(s.key, { start_time: e.target.value })}
                            className="w-28"
                            aria-label={`${day} start`}
                          />
                          <span className="text-muted-foreground">to</span>
                          <Input
                            type="time"
                            value={s.end_time}
                            onChange={(e) => updateSlot(s.key, { end_time: e.target.value })}
                            className="w-28"
                            aria-label={`${day} end`}
                          />
                          {s.is_blocked ? <Badge variant="danger">Blocked</Badge> : null}
                          <Button size="icon" variant="ghost" onClick={() => removeSlot(s.key)} aria-label="Remove">
                            <Trash2 className="h-4 w-4 text-rose-600" />
                          </Button>
                        </div>
                      ))}
                      <Button type="button" size="sm" variant="ghost" onClick={() => addDraft(i)}>
                        <Plus className="h-4 w-4" /> Add {day}
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Public profile</CardTitle>
              <CardDescription>How you appear to patients</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {me ? (
                <>
                  <p className="text-lg font-semibold">{me.full_name}</p>
                  <p className="text-muted-foreground">{me.specialization ?? "—"}</p>
                  <dl className="space-y-1.5">
                    <Row label="Qualification" value={me.qualification} />
                    <Row label="Experience" value={me.years_of_experience ? `${me.years_of_experience} years` : "—"} />
                    <Row label="Hospital" value={me.hospital} />
                    <Row label="Clinic" value={me.clinic_name} />
                    <Row label="Consultation" value={me.consultation_type ? titleCase(me.consultation_type) : "—"} />
                    <Row label="Fee" value={me.consultation_fee != null ? `₹${me.consultation_fee}` : "—"} />
                    <Row label="Languages" value={me.languages} />
                    <Row label="Rating" value={me.rating != null ? `${me.rating} ★` : "New"} />
                  </dl>
                  <p className="text-xs text-muted-foreground">{me.online_consultation_enabled ? "Online consultations enabled" : "Online consultations disabled"}</p>
                </>
              ) : (
                <Spinner className="py-8" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Edit profile</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={saveProfile} className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <PrField name="specialization" label="Specialization" defaultValue={me?.specialization} />
                  <PrField name="qualification" label="Qualification" defaultValue={me?.qualification} />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <PrField name="years_of_experience" label="Years of experience" type="number" defaultValue={me?.years_of_experience?.toString()} />
                  <PrField name="consultation_fee" label="Consultation fee (₹)" type="number" defaultValue={me?.consultation_fee?.toString()} />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <PrField name="hospital" label="Hospital" defaultValue={me?.hospital ?? ""} />
                  <PrField name="clinic_name" label="Clinic name" defaultValue={me?.clinic_name ?? ""} />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="dp-ct">Consultation type</Label>
                    <select id="dp-ct" name="consultation_type" defaultValue={me?.consultation_type ?? ""} className="select">
                      <option value="">—</option>
                      <option value="in_person">In person</option>
                      <option value="online">Online</option>
                      <option value="both">Both</option>
                    </select>
                  </div>
                  <PrField name="languages" label="Languages" defaultValue={me?.languages ?? ""} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="dp-addr">Address</Label>
                  <Input id="dp-addr" name="address" defaultValue={me?.address ?? ""} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="dp-mrn">Medical registration number</Label>
                  <Input id="dp-mrn" name="medical_registration_number" defaultValue={me?.medical_registration_number ?? ""} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="dp-bio">Bio</Label>
                  <Textarea id="dp-bio" name="bio" rows={3} defaultValue={me?.bio ?? ""} />
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="online_consultation_enabled" defaultChecked={!!me?.online_consultation_enabled} className="h-4 w-4 rounded border-border" />
                  Enable online consultations
                </label>
                <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Save profile"}</Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{value || "—"}</dd>
    </div>
  )
}

function PrField({ name, label, type = "text", defaultValue }: { name: string; label: string; type?: string; defaultValue?: string }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={`dp-${name}`}>{label}</Label>
      <Input id={`dp-${name}`} name={name} type={type} defaultValue={defaultValue} />
    </div>
  )
}