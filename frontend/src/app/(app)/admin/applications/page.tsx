"use client"

import { useState } from "react"
import { CheckCircle2, ClipboardCheck, MessageSquareOff, Search, XCircle } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge, statusVariant } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
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
import { formatDate, titleCase } from "@/lib/utils"

interface Application {
  id: number
  user_id: number
  full_name: string | null
  email: string | null
  phone: string | null
  specialization: string
  qualification: string
  medical_registration_number: string
  years_of_experience: number | null
  hospital: string | null
  address: string | null
  consultation_type: string | null
  status: string
  rejection_reason: string | null
  submitted_at: string | null
  reviewed_at: string | null
  documents: string | null
}

export default function ApplicationsPage() {
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [query, setQuery] = useState("")
  const [acting, setActing] = useState(false)

  const { data, loading, error, refetch } = useApi<PaginatedData<Application>>(
    `/admin/doctor/applications?page_size=50${status ? `&status=${status}` : ""}${query ? `&search=${encodeURIComponent(query)}` : ""}`,
  )

  async function review(app: Application, decision: "APPROVED" | "REJECTED", reason?: string) {
    setActing(true)
    try {
      await mutate(`/admin/doctor/applications/${app.id}/review`, {
        method: "POST",
        body: {
          status: decision,
          rejection_reason: decision === "REJECTED" ? reason || null : null,
        },
      })
      toast.success(decision === "APPROVED" ? `Approved ${app.full_name}` : `Rejected ${app.full_name}`)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action failed")
    } finally {
      setActing(false)
    }
  }

  const pending = (data?.items ?? []).filter((a) => a.status === "PENDING")

  return (
    <div className="space-y-6">
      <PageHeader
        title="Doctor applications"
        description="Review and decide on new doctor registrations"
        actions={
          <Badge variant="info" className="text-sm">{pending.length} pending</Badge>
        }
      />

      {error ? <Alert variant="destructive" title="Could not load applications">{error}</Alert> : null}

      <div className="flex flex-wrap gap-2">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search name, email, reg. no."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && setQuery(search)}
          />
        </div>
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-40">
          <option value="">All statuses</option>
          <option value="PENDING">Pending</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
        </Select>
      </div>

      {loading && !data ? <Spinner className="py-10" /> : null}
      {data && data.items.length === 0 ? <EmptyState title="No applications match" /> : null}

      <div className="space-y-4">
        {data?.items.map((app) => (
          <Card key={app.id}>
            <CardContent className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <ClipboardCheck className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="font-medium">{app.full_name ?? "Applicant"}</p>
                    <p className="text-xs text-muted-foreground">{app.email} · {app.phone ?? "no phone"}</p>
                  </div>
                </div>
                <Badge variant={statusVariant(app.status)}>{app.status}</Badge>
              </div>

              <dl className="mt-3 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2 lg:grid-cols-3">
                <Row label="Specialization" value={app.specialization} />
                <Row label="Qualification" value={app.qualification} />
                <Row label="Reg. number" value={app.medical_registration_number} />
                <Row label="Experience" value={app.years_of_experience ? `${app.years_of_experience} years` : "—"} />
                <Row label="Consultation" value={app.consultation_type ? titleCase(app.consultation_type) : "—"} />
                <Row label="Submitted" value={app.submitted_at ? formatDate(app.submitted_at) : "—"} />
              </dl>
              {app.hospital ? <p className="mt-1 text-sm text-muted-foreground">{app.hospital}</p> : null}
              {app.rejection_reason ? <p className="mt-1 text-sm text-rose-600">Reason: {app.rejection_reason}</p> : null}

              {app.status === "PENDING" ? (
                <div className="mt-4 flex gap-2 border-t pt-3">
                  <Button size="sm" onClick={() => review(app, "APPROVED")} disabled={acting}>
                    <CheckCircle2 className="h-4 w-4" /> Approve
                  </Button>
                  <RejectDialog app={app} onReject={(reason) => review(app, "REJECTED", reason)} disabled={acting} />
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function RejectDialog({ app, onReject, disabled }: { app: Application; onReject: (reason?: string) => void; disabled: boolean }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="text-rose-600"><XCircle className="h-4 w-4" /> Reject</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reject {app.full_name}</DialogTitle>
          <DialogDescription>Optionally give a reason the applicant can see.</DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="rev-reason">Rejection reason</Label>
          <Textarea id="rev-reason" name="reason" rows={3} placeholder="e.g. Registration number not verifiable" />
        </div>
        <DialogFooter>
          <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
          <DialogClose asChild>
            <Button
              variant="destructive"
              disabled={disabled}
              onClick={(e) => {
                const el = document.getElementById("rev-reason") as HTMLTextAreaElement | null
                onReject(el?.value || undefined)
              }}
            >
              <MessageSquareOff className="h-4 w-4" /> Reject application
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between gap-2 sm:block">
      <dt className="text-muted-foreground sm:mb-0.5">{label}</dt>
      <dd className="font-medium">{value || "—"}</dd>
    </div>
  )
}