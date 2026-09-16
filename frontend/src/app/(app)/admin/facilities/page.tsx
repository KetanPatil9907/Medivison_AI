"use client"

import { useState } from "react"
import { Building2, Check, Globe, MapPin, Phone, Plus, Star, Trash2 } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"
import type { PaginatedData } from "@/lib/types"
import { titleCase } from "@/lib/utils"

interface Facility {
  id: number
  facility_type: string
  name: string
  address: string | null
  city: string | null
  state: string | null
  country: string | null
  phone: string | null
  email: string | null
  latitude: number | null
  longitude: number | null
  opening_hours: string | null
  website: string | null
  rating: number | null
  is_verified: boolean
  created_at: string | null
}

const TYPES = ["hospital", "clinic", "pharmacy", "lab"]

export default function AdminFacilitiesPage() {
  const [type, setType] = useState("")
  const [saving, setSaving] = useState(false)
  const { data, loading, error, refetch } = useApi<PaginatedData<Facility>>(
    `/healthcare/facilities?page_size=100${type ? `&facility_type=${type}` : ""}`,
  )

  async function createFacility(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setSaving(true)
    try {
      await mutate("/healthcare/admin/facilities", {
        method: "POST",
        body: {
          facility_type: fd.get("facility_type"),
          name: fd.get("name"),
          address: fd.get("address"),
          city: fd.get("city"),
          state: fd.get("state") || null,
          country: fd.get("country") || "India",
          phone: fd.get("phone") || null,
          email: fd.get("email") || null,
          opening_hours: fd.get("opening_hours") || null,
          website: fd.get("website") || null,
          latitude: fd.get("latitude") ? Number(fd.get("latitude")) || null : null,
          longitude: fd.get("longitude") ? Number(fd.get("longitude")) || null : null,
          rating: fd.get("rating") ? Number(fd.get("rating")) || null : null,
          is_verified: fd.get("is_verified") === "on",
        },
      })
      toast.success("Facility added")
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add facility")
    } finally {
      setSaving(false)
    }
  }

  async function toggleVerify(f: Facility) {
    try {
      await mutate(`/healthcare/admin/facilities/${f.facility_type}/${f.id}`, {
        method: "PATCH",
        body: { is_verified: !f.is_verified },
      })
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed")
    }
  }

  async function removeFacility(f: Facility) {
    if (!confirm(`Delete ${f.name}? This cannot be undone.`)) return
    try {
      await mutate(`/healthcare/admin/facilities/${f.facility_type}/${f.id}`, { method: "DELETE" })
      toast.success("Facility deleted")
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete facility")
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Healthcare facilities"
        description="Verify and manage hospitals, clinics, pharmacies and labs"
        actions={
          <Dialog>
            <DialogTrigger asChild>
              <Button><Plus className="h-4 w-4" /> Add facility</Button>
            </DialogTrigger>
            <DialogContent className="max-h-[85vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Add healthcare facility</DialogTitle>
                <DialogDescription>Create a new facility on the platform.</DialogDescription>
              </DialogHeader>
              <form onSubmit={createFacility} className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="fac-type">Type</Label>
                    <Select id="fac-type" name="facility_type" required defaultValue="hospital">
                      {TYPES.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
                    </Select>
                  </div>
                  <FacField name="name" label="Name" required />
                </div>
                <FacField name="address" label="Address" required />
                <div className="grid gap-3 sm:grid-cols-2">
                  <FacField name="city" label="City" required />
                  <div className="grid grid-cols-2 gap-2">
                    <FacField name="state" label="State" />
                    <FacField name="country" label="Country" defaultValue="India" />
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <FacField name="phone" label="Phone" />
                  <FacField name="email" label="Email" />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <FacField name="opening_hours" label="Opening hours" placeholder="e.g. Mon–Sat 9am–6pm" />
                  <FacField name="website" label="Website" />
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <FacField name="latitude" label="Latitude" type="number" step="any" />
                  <FacField name="longitude" label="Longitude" type="number" step="any" />
                  <FacField name="rating" label="Rating (0–5)" type="number" step="any" min={0} max={5} />
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="is_verified" className="h-4 w-4 rounded border-border" />
                  Verified
                </label>
                <DialogFooter>
                  <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
                  <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Add facility"}</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {error ? <Alert variant="destructive" title="Could not load facilities">{error}</Alert> : null}

      <Select value={type} onChange={(e) => setType(e.target.value)} className="w-44">
        <option value="">All types</option>
        {TYPES.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
      </Select>

      {loading && !data ? <Spinner className="py-10" /> : null}
      {data && data.items.length === 0 ? <EmptyState title="No facilities found" /> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data?.items.map((f) => (
          <Card key={`${f.facility_type}-${f.id}`}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Building2 className="h-4 w-4 text-primary" /> {f.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Badge variant="outline" className="capitalize">{f.facility_type}</Badge>
              {f.address ? <p className="flex items-center gap-1.5 text-muted-foreground"><MapPin className="h-3.5 w-3.5" /> {f.address}</p> : null}
              <p className="flex items-center gap-1.5 text-muted-foreground"><Phone className="h-3.5 w-3.5" /> {f.phone ?? "—"}</p>
              {f.website ? <p className="flex items-center gap-1.5 text-muted-foreground"><Globe className="h-3.5 w-3.5" /> {f.website}</p> : null}
              {f.rating != null ? <p className="flex items-center gap-1.5 text-amber-600"><Star className="h-3.5 w-3.5" /> {f.rating}</p> : null}
              <p className="text-xs text-muted-foreground">{f.opening_hours ?? "Hours not set"}</p>
              <div className="flex items-center gap-2 pt-2">
                <Button
                  size="sm"
                  variant={f.is_verified ? "secondary" : "outline"}
                  onClick={() => toggleVerify(f)}
                >
                  <Check className="h-4 w-4" /> {f.is_verified ? "Verified" : "Verify"}
                </Button>
                <Button size="sm" variant="ghost" className="text-rose-600" onClick={() => removeFacility(f)}>
                  <Trash2 className="h-4 w-4" /> Delete
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function FacField({ name, label, type = "text", required, placeholder, defaultValue, min, max, step }: { name: string; label: string; type?: string; required?: boolean; placeholder?: string; defaultValue?: string; min?: number; max?: number; step?: string }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={`fac-${name}`}>{label}</Label>
      <Input id={`fac-${name}`} name={name} type={type} required={required} placeholder={placeholder} defaultValue={defaultValue} min={min} max={max} step={step} />
    </div>
  )
}