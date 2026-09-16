"use client"

import { useState } from "react"
import { HeartPulse, History } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PageHeader } from "@/components/ui/page-header"
import { Select } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"
import type { PaginatedData } from "@/lib/types"
import { formatDate, percentColor, titleCase } from "@/lib/utils"

interface SupportedConditions {
  conditions: Record<string, { label: string; inputs: string[] }>
  engine_mode: string
  disclaimer: string
}

interface RiskFactor {
  factor: string
  value: string | number
  weight: number
  direction: string
}

interface Assessment {
  id: number
  condition_type: string
  risk_level: string
  risk_percentage: number
  factors: RiskFactor[]
  explanation: string | null
  recommendations: string[]
  model_name: string
  is_demo: boolean
  created_at: string | null
}

const INPUT_META: Record<string, { label: string; type: "number" | "select" | "boolean" | "text"; options?: string[]; placeholder?: string }> = {
  age: { label: "Age", type: "number" },
  gender: { label: "Gender", type: "select", options: ["male", "female"] },
  bmi: { label: "BMI (kg/m²)", type: "number", placeholder: "e.g. 24.5" },
  smoker: { label: "Smoker", type: "boolean" },
  family_history: { label: "Family history of condition", type: "boolean" },
  physical_activity: { label: "Physical activity", type: "select", options: ["sedentary", "moderate", "active"] },
  fasting_blood_sugar: { label: "Fasting blood sugar (mg/dL)", type: "number" },
  hba1c: { label: "HbA1c (%)", type: "number" },
  hypertension: { label: "Known hypertension", type: "boolean" },
  diabetes: { label: "Known diabetes", type: "boolean" },
  systolic: { label: "Systolic BP (mmHg)", type: "number" },
  diastolic: { label: "Diastolic BP (mmHg)", type: "number" },
  salt_intake: { label: "Salt intake", type: "select", options: ["low", "moderate", "high"] },
  stress_level: { label: "Stress level (1–10)", type: "number" },
  ldl_cholesterol: { label: "LDL cholesterol (mg/dL)", type: "number" },
  hdl_cholesterol: { label: "HDL cholesterol (mg/dL)", type: "number" },
  triglycerides: { label: "Triglycerides (mg/dL)", type: "number" },
  egfr: { label: "eGFR (mL/min/1.73m²)", type: "number" },
  albumin_creatinine_ratio: { label: "Albumin-creatinine ratio (mg/g)", type: "number" },
}

const LEVEL_VARIANT = { low: "success", moderate: "warning", high: "danger" } as const

export default function RiskPage() {
  const { data: supported, loading: loadingSupported } = useApi<SupportedConditions>("/risk/supported")
  const { data: history, refetch } = useApi<PaginatedData<Assessment>>("/risk/my-assessments?page_size=50")

  const [condition, setCondition] = useState("diabetes")
  const [values, setValues] = useState<Record<string, string | boolean>>({})
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Assessment | null>(null)
  const [tab, setTab] = useState<"run" | "history">("run")

  const inputs = supported?.conditions[condition]?.inputs ?? []

  function setValue(name: string, value: string | boolean) {
    setValues((prev) => ({ ...prev, [name]: value }))
  }

  async function run(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const payload: Record<string, unknown> = {}
    for (const name of inputs) {
      const raw = values[name]
      if (raw === undefined || raw === "" ) continue
      const meta = INPUT_META[name]
      if (meta?.type === "boolean") payload[name] = raw === true || raw === "true"
      else if (!isNaN(Number(raw))) payload[name] = Number(raw)
      else payload[name] = raw
    }
    setRunning(true)
    try {
      const r = await mutate<Assessment>("/risk/predict", {
        method: "POST",
        body: { condition_type: condition, inputs: payload },
      })
      setResult(r)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Risk analysis failed")
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Risk assessment" description="Estimate your risk for common chronic conditions" />

      <Tabs value={tab} onValueChange={(v) => setTab(v as "run" | "history")}>
        <TabsList>
          <TabsTrigger value="run" className="flex items-center gap-1.5"><HeartPulse className="h-4 w-4" /> Run assessment</TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-1.5"><History className="h-4 w-4" /> History</TabsTrigger>
        </TabsList>

        <TabsContent value="run" className="space-y-6">
          {result ? (
            <ResultCard result={result} onReset={() => setResult(null)} />
          ) : loadingSupported ? (
            <Spinner className="py-10" />
          ) : (
            <form onSubmit={run} className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>1 · Choose a condition</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    {supported?.conditions
                      ? Object.entries(supported.conditions).map(([code, info]) => (
                          <button
                            key={code}
                            type="button"
                            onClick={() => {
                              setCondition(code)
                              setResult(null)
                            }}
                            className={`rounded-lg border p-3 text-left transition-colors ${
                              condition === code ? "border-primary bg-primary/5" : "hover:bg-muted"
                            }`}
                          >
                            <p className="text-sm font-medium">{info.label}</p>
                          </button>
                        ))
                      : null}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>2 · Your profile &amp; values</CardTitle>
                  <CardDescription>Fill what you know — blanks are treated as neutral.</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {inputs.map((name) => (
                      <div key={name} className="space-y-1.5">
                        <Label htmlFor={`risk-${name}`}>{INPUT_META[name]?.label ?? titleCase(name)}</Label>
                        {INPUT_META[name]?.type === "select" ? (
                          <Select id={`risk-${name}`} value={String(values[name] ?? "")} onChange={(e) => setValue(name, e.target.value)}>
                            <option value="">Select…</option>
                            {INPUT_META[name].options!.map((o) => (
                              <option key={o} value={o}>{titleCase(o)}</option>
                            ))}
                          </Select>
                        ) : INPUT_META[name]?.type === "boolean" ? (
                          <label className="flex items-center gap-2 rounded-md border p-3">
                            <input
                              type="checkbox"
                              checked={values[name] === true}
                              onChange={(e) => setValue(name, e.target.checked)}
                              className="h-4 w-4 rounded border-border"
                            />
                            <span className="text-sm">Yes</span>
                          </label>
                        ) : (
                          <Input
                            id={`risk-${name}`}
                            type="number"
                            step="any"
                            placeholder={INPUT_META[name]?.placeholder}
                            value={values[name] ? String(values[name]) : ""}
                            onChange={(e) => setValue(name, e.target.value)}
                          />
                        )}
                      </div>
                    ))}
                  </div>

                  <Button type="submit" className="mt-6" disabled={running}>
                    {running ? "Analyzing…" : "Calculate risk"}
                  </Button>
                  <p className="mt-3 text-xs text-muted-foreground">{supported?.disclaimer}</p>
                </CardContent>
              </Card>
            </form>
          )}
        </TabsContent>

        <TabsContent value="history">
          {!history || history.items.length === 0 ? (
            <EmptyState title="No assessments yet" description="Run your first risk assessment to see results here." />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {history.items.map((a) => (
                <Card key={a.id}>
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium">{titleCase(a.condition_type)}</p>
                      <span className={`text-lg font-semibold ${percentColor(a.risk_percentage)}`}>{a.risk_percentage}%</span>
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                      <Badge variant={LEVEL_VARIANT[a.risk_level as keyof typeof LEVEL_VARIANT] ?? "info"}>{a.risk_level}</Badge>
                      <span>{formatDate(a.created_at)}</span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{a.explanation}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function ResultCard({ result, onReset }: { result: Assessment; onReset: () => void }) {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center justify-between gap-2">
            <span className="capitalize">{result.condition_type.replaceAll("_", " ")} risk</span>
            <span className={`text-3xl font-bold ${percentColor(result.risk_percentage)}`}>{result.risk_percentage}%</span>
          </CardTitle>
          <CardDescription>
            <Badge variant={LEVEL_VARIANT[result.risk_level as keyof typeof LEVEL_VARIANT] ?? "info"} className="mr-2">
              {result.risk_level}
            </Badge>
            {result.model_name}{result.is_demo ? " · demo rule-based engine" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="font-medium">Contributing factors</p>
            <ul className="mt-2 divide-y">
              {result.factors.map((f) => (
                <li key={f.factor} className="flex items-center justify-between gap-2 py-2 text-sm">
                  <span className="text-muted-foreground">{f.factor}: <span className="text-foreground">{String(f.value)}</span></span>
                  <span className={`text-xs ${f.direction === "increases" ? "text-rose-600" : "text-muted-foreground"}`}>
                    {f.direction} (+{f.weight})
                  </span>
                </li>
              ))}
            </ul>
          </div>
          {result.explanation ? <p className="text-sm text-muted-foreground">{result.explanation}</p> : null}
          <div>
            <p className="font-medium">Recommendations</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {result.recommendations.map((r, i) => (
                <li key={i} className="text-sm">{r}</li>
              ))}
            </ul>
          </div>
          <Button variant="outline" onClick={onReset}>Run another assessment</Button>
        </CardContent>
      </Card>
    </div>
  )
}