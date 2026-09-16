"use client"

import { useState } from "react"
import { Ban, CheckCircle2, RotateCcw, Search, ShieldCheck, Stethoscope } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge, statusVariant } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageHeader } from "@/components/ui/page-header"
import { Select } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"
import type { PaginatedData } from "@/lib/types"

interface Doctor {
  id: number
  full_name: string
  email: string
  status: string
  specialization: string
  qualification: string | null
  years_of_experience: number | null
  hospital: string | null
  consultation_type: string | null
  rating: number | null
  rating_count: number | null
  created_at: string | null
}

export default function AdminDoctorsPage() {
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [query, setQuery] = useState("")
  const [acting, setActing] = useState(false)

  const { data, loading, error, refetch } = useApi<PaginatedData<Doctor>>(
    `/admin/doctors?page_size=100${status ? `&status=${status}` : ""}${query ? `&search=${encodeURIComponent(query)}` : ""}`,
  )

  async function suspend(d: Doctor) {
    setActing(true)
    try {
      await mutate(`/admin/doctors/${d.id}/suspend`, { method: "PUT", body: { reason: "Suspended by administrator" } })
      toast.success(`${d.full_name} suspended`)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action failed")
    } finally {
      setActing(false)
    }
  }

  async function reactivate(d: Doctor) {
    setActing(true)
    try {
      await mutate(`/admin/doctors/${d.id}/reactivate`, { method: "PUT" })
      toast.success(`${d.full_name} reactivated`)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action failed")
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Doctors"
        description="Manage doctor accounts on the platform"
        actions={<Badge variant="info" className="text-sm">{(data?.total ?? 0).toString()} doctors</Badge>}
      />

      {error ? <Alert variant="destructive" title="Could not load doctors">{error}</Alert> : null}

      <div className="flex flex-wrap gap-2">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search name or email"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && setQuery(search)}
          />
        </div>
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-40">
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="SUSPENDED">Suspended</option>
          <option value="PENDING">Pending</option>
          <option value="REJECTED">Rejected</option>
        </Select>
      </div>

      {loading && !data ? <Spinner className="py-10" /> : null}
      {data && data.items.length === 0 ? <EmptyState title="No doctors found" /> : null}

      <div className="grid gap-4 md:grid-cols-2">
        {data?.items.map((d) => (
          <Card key={d.id}>
            <CardContent className="p-5">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Stethoscope className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="font-medium">{d.full_name}</p>
                    <p className="text-xs text-muted-foreground">{d.email}</p>
                  </div>
                </div>
                <Badge variant={statusVariant(d.status)}>{d.status}</Badge>
              </div>

              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <Row label="Specialization" value={d.specialization} />
                <Row label="Qualification" value={d.qualification} />
                <Row label="Experience" value={d.years_of_experience != null ? `${d.years_of_experience} yrs` : "—"} />
                <Row label="Hospital" value={d.hospital} />
                <Row label="Consultation" value={d.consultation_type ?? "—"} />
                <Row label="Rating" value={d.rating != null ? `${d.rating} ★ (${d.rating_count ?? 0})` : "—"} />
              </dl>

              <div className="mt-4 border-t pt-3">
                {d.status === "ACTIVE" ? (
                  <Button size="sm" variant="outline" className="text-rose-600" onClick={() => suspend(d)} disabled={acting}>
                    <Ban className="h-4 w-4" /> Suspend
                  </Button>
                ) : d.status === "SUSPENDED" ? (
                  <Button size="sm" onClick={() => reactivate(d)} disabled={acting}>
                    <RotateCcw className="h-4 w-4" /> Reactivate
                  </Button>
                ) : (
                  <span className="flex items-center gap-2 text-sm text-muted-foreground">
                    <ShieldCheck className="h-4 w-4" /> {d.status === "APPROVED" ? "" : "Not active"}
                  </span>
                )}
                {d.status === "ACTIVE" ? <CheckCircle2 className="hidden" /> : null}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="truncate font-medium">{value || "—"}</dd>
    </div>
  )
}