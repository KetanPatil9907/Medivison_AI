"use client"

import { useState } from "react"
import { AlertCircle, Ambulance, HeartPulse, MapPin, Phone, ShieldAlert, Siren } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageHeader } from "@/components/ui/page-header"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"

interface Hotline {
  country: string
  label: string
  number: string
  type: string
}

interface Hotlines {
  hotlines: Hotline[]
  universal: string
  disclaimer: string
}

interface Protocol {
  id: string
  title: string
  steps: string[]
  caution: string | null
}

interface Protocols {
  protocols: Protocol[]
  disclaimer: string
}

interface SosResult {
  message: string
  contacts_notified: number
  emergency_numbers: { label: string; number: string }[]
  [key: string]: unknown
}

export default function EmergencyPage() {
  const { data: hotlines } = useApi<Hotlines>("/emergency/hotlines")
  const { data: protocols } = useApi<Protocols>("/emergency/protocols")
  const [tab, setTab] = useState<"protocols" | "sos">("protocols")
  const [sending, setSending] = useState(false)
  const [note, setNote] = useState("")
  const [sosResult, setSosResult] = useState<SosResult | null>(null)

  async function sendSos(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSending(true)
    setSosResult(null)
    try {
      const r = await mutate<SosResult>("/emergency/sos", { method: "POST", body: { note: note || null } })
      setSosResult(r)
      toast.success("SOS alerts sent")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not send SOS")
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Emergency" description="First aid, hotlines, and one-tap SOS" />

      <Card className="border-rose-200 bg-rose-50">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-rose-600 text-white">
              <Siren className="h-5 w-5" />
            </span>
            <div>
              <p className="font-semibold text-rose-900">Call 112</p>
              <p className="text-sm text-rose-700">Universal emergency number — routes to your local services.</p>
            </div>
          </div>
          <a href="tel:112" className="inline-flex items-center gap-2 rounded-md bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700">
            <Phone className="h-4 w-4" /> Call now
          </a>
        </CardContent>
      </Card>

      <Tabs value={tab} onValueChange={(v) => setTab(v as "protocols" | "sos")}>
        <TabsList>
          <TabsTrigger value="protocols" className="flex items-center gap-1.5"><HeartPulse className="h-4 w-4" /> First aid</TabsTrigger>
          <TabsTrigger value="sos" className="flex items-center gap-1.5"><AlertCircle className="h-4 w-4" /> My SOS</TabsTrigger>
        </TabsList>

        <TabsContent value="protocols" className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            {protocols?.protocols.map((p) => (
              <Card key={p.id}>
                <CardHeader>
                  <CardTitle className="text-base">{p.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <ol className="list-decimal space-y-1 pl-5 text-sm">
                    {p.steps.map((s, i) => <li key={i}>{s}</li>)}
                  </ol>
                  {p.caution ? (
                    <p className="mt-3 flex items-start gap-2 text-sm text-rose-700">
                      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" /> {p.caution}
                    </p>
                  ) : null}
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Emergency hotlines</CardTitle>
              <CardDescription>{hotlines?.universal}</CardDescription>
            </CardHeader>
            <CardContent>
              {!hotlines ? <Spinner className="py-6" /> : null}
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {hotlines?.hotlines.map((h, i) => (
                  <a key={i} href={`tel:${h.number}`} className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted">
                    <div>
                      <p className="text-sm font-medium">{h.label}</p>
                      <p className="text-xs text-muted-foreground capitalize">{h.type} · {h.country}</p>
                    </div>
                    <span className="text-sm font-semibold text-rose-600">{h.number}</span>
                  </a>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sos" className="space-y-6">
          {!sosResult ? (
            <Card>
              <CardHeader>
                <CardTitle>Trigger SOS alert</CardTitle>
                <CardDescription>Alerts your saved emergency contacts and nearby support.</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={sendSos} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="sos-note">What&apos;s happening? (optional)</Label>
                    <Input id="sos-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. chest pain at home" />
                  </div>
                  <Button type="submit" variant="destructive" disabled={sending} className="w-full">
                    <Siren className="h-4 w-4" /> {sending ? "Sending alerts…" : "Send SOS"}
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    Only use this in a genuine emergency. Make sure your emergency contacts are up to date in your profile.
                  </p>
                </form>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-emerald-700">SOS alerts sent</CardTitle>
                <CardDescription>{sosResult.message}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="font-medium">Where to go now</p>
                  <ul className="mt-2 space-y-2">
                    {(sosResult.emergency_numbers ?? []).map((n, i) => (
                      <li key={i} className="flex items-center justify-between rounded-lg border p-3">
                        <span className="text-sm">{n.label}</span>
                        <a href={`tel:${n.number}`} className="text-sm font-semibold text-rose-600">{n.number}</a>
                      </li>
                    ))}
                  </ul>
                </div>
                <Alert variant="success" title="Help is on the way">
                  Contacts notified: {sosResult.contacts_notified}. Stay in a safe place and keep your phone on.
                </Alert>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Ambulance className="h-4 w-4" /> Nearest help</CardTitle>
              <CardDescription>Use your profile location to find nearby facilities.</CardDescription>
            </CardHeader>
            <CardContent>
              <EmptyState title="Enable location search" description="Nearby facilities need your GPS position — allow location to search within 25 km." />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {protocols?.disclaimer ? (
        <p className="text-xs text-muted-foreground">{protocols.disclaimer}</p>
      ) : null}
    </div>
  )
}