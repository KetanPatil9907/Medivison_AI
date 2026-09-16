"use client"

import { useMemo, useState } from "react"
import {
  CalendarDays,
  Clock,
  MapPin,
  ShieldAlert,
  Stethoscope,
  Video,
  Phone,
} from "lucide-react"

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
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/toast"
import { useApi, mutate } from "@/hooks/use-api"
import { apiFetch } from "@/lib/api"
import type { PaginatedData } from "@/lib/types"
import { formatDate } from "@/lib/utils"

interface Appointment {
  id: number
  scheduled_date: string
  start_time: string
  end_time: string
  duration_minutes: number
  consultation_type: string
  status: string
  reason: string | null
  queue_position: number | null
  doctor: { id: number; full_name: string; specialization: string; hospital: string } | null
}

interface DoctorCard {
  id: number
  full_name: string
  specialization: string
  qualification: string
  hospital: string | null
  consultation_type: string
  rating: number
  years_of_experience: number | null
}

interface Slot {
  start_time: string
  end_time: string
  available: boolean
}

const TYPE_ICON = { in_person: MapPin, online: Video, phone: Phone } as const

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

export default function AppointmentsPage() {
  const [tab, setTab] = useState<"upcoming" | "book">("upcoming")
  const { data, loading, error, refetch } = useApi<PaginatedData<Appointment>>(
    "/appointments/my?page_size=100&upcoming=true",
  )
  const { data: history } = useApi<PaginatedData<Appointment>>("/appointments/my?page_size=50")
  const { data: doctors } = useApi<PaginatedData<DoctorCard>>("/doctors?page_size=100")

  const [bookDoctor, setBookDoctor] = useState("")
  const [bookDate, setBookDate] = useState(todayStr())
  const [slots, setSlots] = useState<Slot[] | null>(null)
  const [bookTime, setBookTime] = useState("")
  const [bookType, setBookType] = useState("in_person")
  const [bookReason, setBookReason] = useState("")
  const [booking, setBooking] = useState(false)

  const [openId, setOpenId] = useState<number | null>(null)
  const [action, setAction] = useState<"cancel" | "reschedule" | null>(null)
  const [actionValue, setActionValue] = useState("")
  const [newDate, setNewDate] = useState(todayStr())
  const [newTime, setNewTime] = useState("")
  const [actionBusy, setActionBusy] = useState(false)

  const active = useMemo(
    () => (data?.items ?? []).filter((a) => a.status !== "CANCELLED"),
    [data],
  )

  async function loadSlots(doctorId: string, date: string) {
    if (!doctorId) return
    setSlots(null)
    try {
      const result = await apiFetch<Slot[]>(`/appointments/slots?doctor_id=${doctorId}&date=${date}`)
      setSlots(result)
      setBookTime("")
    } catch {
      setSlots([])
      toast.error("Could not load available slots")
    }
  }

  async function submitBooking(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!bookDoctor || !bookTime) {
      toast.error("Pick a doctor, date, and a slot to book")
      return
    }
    setBooking(true)
    try {
      await mutate("/appointments", {
        method: "POST",
        body: {
          doctor_id: Number(bookDoctor),
          scheduled_date: bookDate,
          start_time: bookTime,
          consultation_type: bookType,
          reason: bookReason || null,
        },
      })
      toast.success("Appointment requested")
      setTab("upcoming")
      setActionValue("")
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Booking failed")
    } finally {
      setBooking(false)
    }
  }

  async function runAction(appointment: Appointment) {
    if (!openId) return
    setActionBusy(true)
    try {
      if (action === "cancel") {
        await mutate(`/appointments/${openId}/cancel`, {
          method: "PATCH",
          body: { reason: actionValue || "No reason provided" },
        })
        toast.success("Appointment cancelled")
      } else if (action === "reschedule") {
        await mutate(`/appointments/${openId}/reschedule`, {
          method: "PATCH",
          body: { scheduled_date: newDate, start_time: newTime },
        })
        toast.success("Appointment rescheduled")
      }
      setOpenId(null)
      setAction(null)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action failed")
    } finally {
      setActionBusy(false)
    }
  }

  const selectedDoctor = doctors?.items.find((d) => String(d.id) === bookDoctor)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Appointments"
        description="Book, cancel, or reschedule visits"
        actions={<Button onClick={() => setTab(tab === "book" ? "upcoming" : "book")}>{tab === "book" ? "My appointments" : "Book new"}</Button>}
      />

      {error ? <Alert variant="destructive" title="Could not load appointments">{error}</Alert> : null}

      {tab === "upcoming" ? (
        <>
          {loading && !data ? <Spinner className="py-10" /> : null}
          {active.length === 0 && !loading ? (
            <EmptyState title="No upcoming appointments" description="Book an appointment with a doctor to get started." />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {active.map((a) => {
                const Icon = TYPE_ICON[a.consultation_type as keyof typeof TYPE_ICON] ?? CalendarDays
                return (
                  <Card key={a.id}>
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-3">
                          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                            <Stethoscope className="h-4 w-4" />
                          </span>
                          <div>
                            <p className="font-medium">{a.doctor?.full_name ?? "Doctor"}</p>
                            <p className="text-xs text-muted-foreground">
                              {a.doctor?.specialization ?? "General"} · {a.doctor?.hospital ?? "—"}
                            </p>
                          </div>
                        </div>
                        <Badge variant={statusVariant(a.status)}>{a.status}</Badge>
                      </div>
                      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1.5">
                          <CalendarDays className="h-3.5 w-3.5" /> {formatDate(a.scheduled_date)}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5" /> {a.start_time}–{a.end_time}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <Icon className="h-3.5 w-3.5" /> {a.consultation_type}
                        </span>
                        {a.queue_position ? <span className="flex items-center gap-1.5">Queue #{a.queue_position}</span> : null}
                      </div>
                      {a.reason ? <p className="mt-3 text-sm text-muted-foreground">{a.reason}</p> : null}
                      {["BOOKED", "CONFIRMED", "RESCHEDULED"].includes(a.status) ? (
                        <div className="mt-4 flex gap-2">
                          <Dialog open={openId === a.id && action === "cancel"} onOpenChange={(open) => { setOpenId(open ? a.id : null); setAction(open ? "cancel" : null) }}>
                            <DialogTrigger asChild>
                              <Button variant="outline" size="sm">Cancel</Button>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Cancel appointment</DialogTitle>
                                <DialogDescription>Let the clinic know why you&apos;re cancelling.</DialogDescription>
                              </DialogHeader>
                              <Textarea value={actionValue} onChange={(e) => setActionValue(e.target.value)} rows={3} placeholder="Reason (optional)" />
                              <DialogFooter>
                                <DialogClose asChild><Button variant="outline">Close</Button></DialogClose>
                                <Button variant="destructive" disabled={actionBusy} onClick={() => runAction(a)}>
                                  {actionBusy ? "Cancelling…" : "Cancel appointment"}
                                </Button>
                              </DialogFooter>
                            </DialogContent>
                          </Dialog>
                          <Dialog open={openId === a.id && action === "reschedule"} onOpenChange={(open) => { setOpenId(open ? a.id : null); setAction(open ? "reschedule" : null) }}>
                            <DialogTrigger asChild>
                              <Button variant="outline" size="sm">Reschedule</Button>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Reschedule appointment</DialogTitle>
                                <DialogDescription>Pick a new date and time.</DialogDescription>
                              </DialogHeader>
                              <div className="space-y-3">
                                <div className="space-y-1.5">
                                  <Label htmlFor="reschedule-date">New date</Label>
                                  <Input id="reschedule-date" type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} />
                                </div>
                                <div className="space-y-1.5">
                                  <Label htmlFor="reschedule-time">New time</Label>
                                  <Input id="reschedule-time" type="time" value={newTime} onChange={(e) => setNewTime(e.target.value)} />
                                </div>
                              </div>
                              <DialogFooter>
                                <DialogClose asChild><Button variant="outline">Close</Button></DialogClose>
                                <Button disabled={actionBusy || !newDate || !newTime} onClick={() => runAction(a)}>
                                  {actionBusy ? "Rescheduling…" : "Reschedule"}
                                </Button>
                              </DialogFooter>
                            </DialogContent>
                          </Dialog>
                        </div>
                      ) : null}
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Appointment history</CardTitle>
            </CardHeader>
            <CardContent>
              {!history || history.items.length === 0 ? (
                <EmptyState title="No past appointments" />
              ) : (
                <ul className="divide-y">
                  {history.items.map((a) => (
                    <li key={a.id} className="flex items-center justify-between gap-2 py-2.5">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{a.doctor?.full_name ?? "Doctor"}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatDate(a.scheduled_date)} · {a.start_time}
                        </p>
                      </div>
                      <Badge variant={statusVariant(a.status)}>{a.status}</Badge>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      ) : (
        <form onSubmit={submitBooking} className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Book an appointment</CardTitle>
              <CardDescription>Select a doctor, date, and an available slot.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="book-doctor">Doctor</Label>
                <Select
                  id="book-doctor"
                  value={bookDoctor}
                  onChange={(e) => {
                    setBookDoctor(e.target.value)
                    loadSlots(e.target.value, bookDate)
                  }}
                  required
                >
                  <option value="">Select a doctor…</option>
                  {doctors?.items.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.full_name} — {d.specialization}
                    </option>
                  ))}
                </Select>
              </div>

              {selectedDoctor ? (
                <div className="flex items-start gap-2 rounded-lg bg-muted p-3 text-sm">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  <p className="text-muted-foreground">
                    {selectedDoctor.qualification ?? "Doctor"} · {selectedDoctor.years_of_experience ?? "—"} yrs experience · rating{" "}
                    {selectedDoctor.rating.toFixed(1)}
                  </p>
                </div>
              ) : null}

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="book-date">Date</Label>
                  <Input
                    id="book-date"
                    type="date"
                    value={bookDate}
                    min={todayStr()}
                    onChange={(e) => {
                      setBookDate(e.target.value)
                      loadSlots(bookDoctor, e.target.value)
                    }}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="book-type">Consultation</Label>
                  <Select id="book-type" value={bookType} onChange={(e) => setBookType(e.target.value)}>
                    <option value="in_person">In person</option>
                    <option value="online">Online</option>
                    <option value="phone">Phone</option>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label>Available slots{slots ? ` — ${slots.filter((s) => s.available).length} open` : ""}</Label>
                {!slots ? (
                  <p className="text-sm text-muted-foreground">Choose a doctor and date to see slots.</p>
                ) : slots.filter((s) => s.available).length === 0 ? (
                  <p className="text-sm text-muted-foreground">No slots available on this date.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {slots
                      .filter((s) => s.available)
                      .map((s) => (
                        <button
                          key={s.start_time}
                          type="button"
                          onClick={() => setBookTime(s.start_time)}
                          className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                            bookTime === s.start_time
                              ? "border-primary bg-primary text-primary-foreground"
                              : "hover:bg-muted"
                          }`}
                        >
                          {s.start_time}
                        </button>
                      ))}
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="book-reason">Reason for visit</Label>
                <Textarea
                  id="book-reason"
                  value={bookReason}
                  onChange={(e) => setBookReason(e.target.value)}
                  rows={3}
                  placeholder="Briefly describe your concern"
                />
              </div>

              <Button type="submit" disabled={booking || !slots || slots.length === 0}>
                {booking ? "Booking…" : "Request appointment"}
              </Button>
            </CardContent>
          </Card>
        </form>
      )}
    </div>
  )
}