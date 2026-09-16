"use client"

import { useState } from "react"
import { Building2, FlaskConical, Hospital, MapPin, Pill as PillIcon, Stethoscope, Store } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Select } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useApi } from "@/hooks/use-api"
import type { PaginatedData } from "@/lib/types"

const FACILITY_META = {
  hospital: { label: "Hospitals", icon: Hospital, hint: "beds, ICU, emergency" },
  clinic: { label: "Clinics", icon: Stethoscope, hint: "specialties" },
  pharmacy: { label: "Pharmacies", icon: PillIcon, hint: "delivery, license" },
  lab: { label: "Labs", icon: FlaskConical, hint: "tests offered" },
} as const

type FacilityRow = {
  id: number
  facility_type: string
  name: string
  address: string | null
  city: string | null
  phone: string | null
  email: string | null
  opening_hours: string | null
  website: string | null
  rating: number | null
  is_verified: boolean
  distance_km: number | null
  total_beds?: number
  available_beds?: number
  has_emergency?: boolean
}

interface Service {
  id: number
  facility_type: string
  facility_id: number
  service_name: string
  description: string | null
  price: number | null
  is_active: boolean
}

type ServiceRow = Service

export default function HealthcarePage() {
  const [tab, setTab] = useState<"facilities" | "services">("facilities")
  const [type, setType] = useState<string>("hospital")
  const [search, setSearch] = useState("")
  const [query, setQuery] = useState("")
  const { data: facilities, loading, error } = useApi<PaginatedData<FacilityRow>>(
    query || type ? `/healthcare/facilities?page_size=50${type ? `&facility_type=${type}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}` : null,
  )
  const { data: services } = useApi<PaginatedData<ServiceRow>>("/healthcare/services?page_size=100")

  const list = facilities?.items ?? []

  return (
    <div className="space-y-6">
      <PageHeader title="Healthcare directory" description="Find hospitals, clinics, pharmacies, and labs near you" />

      {error ? <Alert variant="destructive" title="Could not load directory">{error}</Alert> : null}

      <Tabs value={tab} onValueChange={(v) => setTab(v as "facilities" | "services")}>
        <TabsList>
          <TabsTrigger value="facilities" className="flex items-center gap-1.5"><Building2 className="h-4 w-4" /> Facilities</TabsTrigger>
          <TabsTrigger value="services" className="flex items-center gap-1.5"><Store className="h-4 w-4" /> Services</TabsTrigger>
        </TabsList>

        <TabsContent value="facilities" className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <Select value={type} onChange={(e) => setType(e.target.value)} className="w-40">
              {Object.entries(FACILITY_META).map(([key, meta]) => (
                <option key={key} value={key}>{meta.label}</option>
              ))}
            </Select>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                setQuery(search)
              }}
              className="flex flex-1 gap-2"
            >
              <Input placeholder="Search by name or city" value={search} onChange={(e) => setSearch(e.target.value)} />
              <Button type="submit" variant="outline">Search</Button>
            </form>
          </div>

          {loading && !facilities ? <Spinner className="py-10" /> : null}
          {list.length === 0 && !loading ? <EmptyState title="No facilities found" description="Try a different type or search term." /> : null}

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {list.map((f) => {
              const Icon = FACILITY_META[f.facility_type as keyof typeof FACILITY_META]?.icon ?? Building2
              return (
                <Card key={f.id}>
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                          <Icon className="h-4 w-4" />
                        </span>
                        <div className="min-w-0">
                          <p className="truncate font-medium">{f.name}</p>
                          <p className="text-xs text-muted-foreground capitalize">{f.facility_type}</p>
                        </div>
                      </div>
                      {f.is_verified ? <Badge variant="success">Verified</Badge> : <Badge variant="outline">Unverified</Badge>}
                    </div>
                    <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                      {f.address ? (
                        <p className="flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5" /> {f.address}{f.city ? `, ${f.city}` : ""}</p>
                      ) : null}
                      {f.phone ? <p className="flex items-center gap-1.5">{f.phone}</p> : null}
                      {f.distance_km !== null ? <p className="text-xs">{f.distance_km} km away</p> : null}
                      {f.rating ? <p className="text-xs">Rating {Number(f.rating).toFixed(1)}</p> : null}
                      {f.opening_hours ? <p className="text-xs">Hours: {String(f.opening_hours)}</p> : null}
                      {f.facility_type === "hospital" && f.total_beds ? (
                        <p className="text-xs">Beds available: {f.available_beds ?? "—"} / {f.total_beds}</p>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </TabsContent>

        <TabsContent value="services">
          {!services || services.items.length === 0 ? <EmptyState title="No services listed yet" /> : null}
          {services && services.items.length > 0 ? (
            <Card>
              <CardContent className="divide-y">
                {services.items.map((s) => (
                  <div key={s.id} className="flex items-center justify-between gap-2 py-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{s.service_name}</p>
                        <Badge variant="outline" className="capitalize">{s.facility_type}</Badge>
                      </div>
                      {s.description ? <p className="mt-0.5 text-sm text-muted-foreground">{s.description}</p> : null}
                    </div>
                    {s.price !== null ? <span className="shrink-0 text-sm font-semibold">₹{Number(s.price)}</span> : null}
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  )
}