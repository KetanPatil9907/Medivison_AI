"use client"

import { useState } from "react"
import { Brain, History, RotateCcw } from "lucide-react"

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
import { useApi } from "@/hooks/use-api"
import { mutate } from "@/hooks/use-api"
import type { PaginatedData } from "@/lib/types"
import { formatDate } from "@/lib/utils"

interface ConditionResult {
  id: number
  condition_name: string
  confidence: number
  severity: string
  recommended_specialty: string | null
  emergency_flag: boolean
  advice: string | null
  model: string
}

interface Session {
  id: number
  mode: string
  status: string
  symptoms_text: string | null
  duration_days: number | null
  selected_symptoms: string[]
  emergency_flag: boolean
  results: ConditionResult[]
  created_at: string | null
}

const COMMON_SYMPTOMS = [
  "fever", "headache", "cough", "fatigue", "nausea", "body ache", "sore throat",
  "shortness of breath", "chest pain", "dizziness", "vomiting", "runny nose",
  "abdominal pain", "rash", "chills", "sweating", "loss of appetite", "pain in joints",
]

export default function SymptomsPage() {
  const { data, refetch } = useApi<PaginatedData<Session>>("/symptoms/my-sessions?page_size=50")
  const [tab, setTab] = useState<"check" | "history">("check")
  const [selected, setSelected] = useState<string[]>([])
  const [symptomsText, setSymptomsText] = useState("")
  const [durationDays, setDurationDays] = useState<number | null>(null)
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState<Session | null>(null)

  function toggle(symptom: string) {
    setSelected((prev) => (prev.includes(symptom) ? prev.filter((s) => s !== symptom) : [...prev, symptom]))
  }

  async function run(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (selected.length === 0) {
      toast.error("Pick at least one symptom")
      return
    }
    setChecking(true)
    setResult(null)
    try {
      const r = await mutate<Session>("/symptoms/check", {
        method: "POST",
        body: { symptoms: selected, symptoms_text: symptomsText || null, duration_days: durationDays },
      })
      setResult(r)
      refetch()
      setTab("check")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Checker failed")
    } finally {
      setChecking(false)
    }
  }

  function reset() {
    setSelected([])
    setSymptomsText("")
    setDurationDays(null)
    setResult(null)
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Symptom checker" description="Share how you feel and let AI suggest likely causes" />

      <Tabs value={tab} onValueChange={(v) => setTab(v as "check" | "history")}>
        <TabsList>
          <TabsTrigger value="check" className="flex items-center gap-1.5"><Brain className="h-4 w-4" /> Check now</TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-1.5"><History className="h-4 w-4" /> History</TabsTrigger>
        </TabsList>

        <TabsContent value="check" className="space-y-6">
          {result ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  Possible conditions
                  {result.emergency_flag ? <Badge variant="danger">Seek urgent care</Badge> : null}
                </CardTitle>
                <CardDescription>
                  {result.results.length} likely causes · {formatDate(result.created_at)}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {result.emergency_flag ? (
                  <Alert variant="warning" title="Emergency symptoms detected">
                    Your symptoms could indicate a serious condition. Please contact emergency services or visit the nearest
                    emergency department immediately.
                  </Alert>
                ) : null}
                {result.results.map((r) => (
                  <div key={r.id} className="rounded-lg border p-4">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium">{r.condition_name}</p>
                      <Badge variant={r.severity === "severe" ? "danger" : r.severity === "moderate" ? "warning" : "info"}>
                        {Math.round(r.confidence * 100)}% · {r.severity}
                      </Badge>
                    </div>
                    {r.recommended_specialty ? (
                      <p className="mt-1 text-sm text-muted-foreground">Specialist: {r.recommended_specialty}</p>
                    ) : null}
                    {r.advice ? <p className="mt-2 text-sm">{r.advice}</p> : null}
                  </div>
                ))}
                <p className="text-xs text-muted-foreground">
                  Powered by {result.results.map((r) => r.model).filter((v, i, a) => a.indexOf(v) === i).join(", ")}. This is
                  screening guidance, not a diagnosis.
                </p>
                <Button variant="outline" onClick={reset}>
                  <RotateCcw className="h-4 w-4" /> Check again
                </Button>
              </CardContent>
            </Card>
          ) : (
            <form onSubmit={run} className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Select your symptoms</CardTitle>
                  <CardDescription>Choose all that apply — you can also type them below.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex flex-wrap gap-2">
                    {COMMON_SYMPTOMS.map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => toggle(s)}
                        className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                          selected.includes(s) ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted"
                        }`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="sx-text">Describe in your own words (optional)</Label>
                    <Input
                      id="sx-text"
                      value={symptomsText}
                      onChange={(e) => setSymptomsText(e.target.value)}
                      placeholder="e.g. sharp pain behind my left ear since yesterday"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="sx-days">How many days have you felt this way?</Label>
                    <Input
                      id="sx-days"
                      type="number"
                      min={0}
                      max={3650}
                      value={durationDays ?? ""}
                      onChange={(e) => setDurationDays(e.target.value ? Number(e.target.value) : null)}
                      placeholder="Optional"
                    />
                  </div>
                  <Button type="submit" disabled={checking || selected.length === 0}>
                    {checking ? "Analyzing…" : "Check symptoms"}
                  </Button>
                </CardContent>
              </Card>
            </form>
          )}
        </TabsContent>

        <TabsContent value="history">
          {!data || data.items.length === 0 ? (
            <EmptyState title="No symptom checks yet" />
          ) : (
            <Card>
              <CardContent className="divide-y">
                {data.items.map((s) => (
                  <div key={s.id} className="py-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">
                        {s.selected_symptoms.length > 0
                          ? s.selected_symptoms.slice(0, 3).join(", ")
                          : s.symptoms_text ?? "Symptoms"}
                      </p>
                      {s.emergency_flag ? <Badge variant="danger">Urgent</Badge> : null}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(s.created_at)} · Top match: {s.results[0]?.condition_name ?? "—"} (
                      {s.results[0] ? Math.round(s.results[0].confidence * 100) : 0}%)
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}