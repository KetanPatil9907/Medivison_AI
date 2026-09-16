"use client"

import { useState } from "react"
import { ChefHat, History, UtensilsCrossed } from "lucide-react"

import { Alert } from "@/components/ui/alert"
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
import { formatDate, titleCase } from "@/lib/utils"

const GOALS = ["maintain", "weight_loss", "weight_gain", "muscle_gain"]
const PREFERENCES = ["non_vegetarian", "vegetarian", "vegan"]
const ACTIVITY = ["sedentary", "light", "moderate", "active", "very_active"]

interface CalculatorResult {
  bmi: number
  bmr: number
  tdee: number
  [key: string]: number | string | undefined
}

interface MealItem {
  item: string
  quantity?: string
  calories?: number
}

interface DietPlan {
  id: number
  plan_date: string | null
  bmi: number | null
  bmr: number | null
  tdee: number | null
  calorie_target: number | null
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
  water_liters: number | null
  goal: string
  dietary_preference: string
  breakfast: MealItem[]
  lunch: MealItem[]
  dinner: MealItem[]
  snacks: MealItem[]
  created_at: string | null
}

export default function DietPage() {
  const { data: plans, loading, refetch } = useApi<PaginatedData<DietPlan>>("/diet/plans?page_size=20")
  const [tab, setTab] = useState<"plan" | "history">("plan")
  const [cal, setCal] = useState<CalculatorResult | null>(null)
  const [run, setRun] = useState<DietPlan | null>(null)
  const [busy, setBusy] = useState<"calc" | "plan" | null>(null)
  const [goal, setGoal] = useState("maintain")
  const [preference, setPreference] = useState("non_vegetarian")
  const [activity, setActivity] = useState("moderate")

  async function calculate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setBusy("calc")
    try {
      const params = new URLSearchParams({
        height_cm: fd.get("height_cm") as string,
        weight_kg: fd.get("weight_kg") as string,
        age: fd.get("age") as string,
        gender: fd.get("gender") as string,
        activity_level: fd.get("activity_level") as string,
      })
      const r = await mutate<CalculatorResult>(`/diet/calculator?${params.toString()}`)
      setCal(r)
      toast.success("Calories calculated")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Calculation failed")
    } finally {
      setBusy(null)
    }
  }

  async function generatePlan() {
    setBusy("plan")
    try {
      const r = await mutate<DietPlan>("/diet/plan", {
        method: "POST",
        body: { goal, dietary_preference: preference, activity_level: activity },
      })
      setRun(r)
      refetch()
      toast.success("Diet plan generated")
      setTab("plan")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not generate plan")
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Diet & nutrition" description="Calculate your needs and get a personalised meal plan" />

      <Tabs value={tab} onValueChange={(v) => setTab(v as "plan" | "history")}>
        <TabsList>
          <TabsTrigger value="plan" className="flex items-center gap-1.5"><ChefHat className="h-4 w-4" /> Plan</TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-1.5"><History className="h-4 w-4" /> History</TabsTrigger>
        </TabsList>

        <TabsContent value="plan" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><UtensilsCrossed className="h-4 w-4" /> Calorie calculator</CardTitle>
                <CardDescription>Estimate BMR and TDEE — our plans build on this.</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={calculate} className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Field name="height_cm" label="Height (cm)" type="number" min={1} max={250} />
                    <Field name="weight_kg" label="Weight (kg)" type="number" min={1} max={400} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Field name="age" label="Age" type="number" min={10} max={120} />
                    <div className="space-y-1.5">
                      <Label htmlFor="gender">Gender</Label>
                      <Select id="gender" name="gender" defaultValue="male">
                        <option value="male">Male</option>
                        <option value="female">Female</option>
                      </Select>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="act">Activity level</Label>
                    <Select id="act" name="activity_level" defaultValue="moderate">
                      {ACTIVITY.map((a) => <option key={a} value={a}>{titleCase(a)}</option>)}
                    </Select>
                  </div>
                  <Button type="submit" disabled={busy === "calc"}>{busy === "calc" ? "Calculating…" : "Calculate"}</Button>
                </form>
                {cal ? (
                  <div className="mt-4 grid grid-cols-3 gap-2 rounded-lg bg-muted p-3 text-center">
                    <div>
                      <p className="text-lg font-semibold">{cal.bmi?.toFixed(1)}</p>
                      <p className="text-xs text-muted-foreground">BMI</p>
                    </div>
                    <div>
                      <p className="text-lg font-semibold">{Math.round(cal.bmr ?? 0)}</p>
                      <p className="text-xs text-muted-foreground">BMR kcal</p>
                    </div>
                    <div>
                      <p className="text-lg font-semibold">{Math.round(cal.tdee ?? 0)}</p>
                      <p className="text-xs text-muted-foreground">TDEE kcal</p>
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Generate a meal plan</CardTitle>
                <CardDescription>AI builds a full-day menu around your goals.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="goal">Goal</Label>
                  <Select id="goal" value={goal} onChange={(e) => setGoal(e.target.value)}>
                    {GOALS.map((g) => <option key={g} value={g}>{titleCase(g)}</option>)}
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="pref">Dietary preference</Label>
                  <Select id="pref" value={preference} onChange={(e) => setPreference(e.target.value)}>
                    {PREFERENCES.map((p) => <option key={p} value={p}>{titleCase(p)}</option>)}
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="act2">Activity level</Label>
                  <Select id="act2" value={activity} onChange={(e) => setActivity(e.target.value)}>
                    {ACTIVITY.map((a) => <option key={a} value={a}>{titleCase(a)}</option>)}
                  </Select>
                </div>
                <Button onClick={generatePlan} disabled={busy !== null}>
                  {busy === "plan" ? "Building plan…" : "Generate plan"}
                </Button>
              </CardContent>
            </Card>
          </div>

          {run ? <PlanCard plan={run} /> : null}
        </TabsContent>

        <TabsContent value="history">
          {loading ? <Spinner className="py-10" /> : null}
          {plans && plans.items.length === 0 ? <EmptyState title="No diet plans yet" /> : null}
          {plans && plans.items.length > 0 ? (
            <div className="space-y-4">
              {plans.items.map((p) => <PlanCard key={p.id} plan={p} />)}
            </div>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function PlanCard({ plan }: { plan: DietPlan }) {
  const macros = [
    { label: "Calories", value: plan.calorie_target, unit: "kcal" },
    { label: "Protein", value: plan.protein_g, unit: "g" },
    { label: "Carbs", value: plan.carbs_g, unit: "g" },
    { label: "Fat", value: plan.fat_g, unit: "g" },
    { label: "Water", value: plan.water_liters, unit: "L" },
  ]
  const meals = [
    { title: "Breakfast", items: plan.breakfast },
    { title: "Lunch", items: plan.lunch },
    { title: "Dinner", items: plan.dinner },
    { title: "Snacks", items: plan.snacks },
  ]
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-2">
          <span>Daily plan</span>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{titleCase(plan.goal)}</Badge>
            <Badge variant="outline">{titleCase(plan.dietary_preference)}</Badge>
          </div>
        </CardTitle>
        <CardDescription>{plan.plan_date ? formatDate(plan.plan_date) : ""} · BMI {plan.bmi?.toFixed(1) ?? "—"} · BMR {Math.round(plan.bmr ?? 0)} · TDEE {Math.round(plan.tdee ?? 0)}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {macros.map((m) => (
            <div key={m.label} className="rounded-lg bg-muted p-2 text-center">
              <p className="text-sm font-semibold">{m.value ?? "—"} <span className="text-xs text-muted-foreground">{m.unit}</span></p>
              <p className="text-xs text-muted-foreground">{m.label}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {meals.map((meal) => (
            <div key={meal.title} className="rounded-lg border p-3">
              <p className="text-sm font-medium">{meal.title}</p>
              {meal.items.length === 0 ? <p className="text-xs text-muted-foreground">—</p> : null}
              <ul className="mt-1 space-y-0.5 text-sm text-muted-foreground">
                {meal.items.map((i, idx) => (
                  <li key={idx}>
                    {i.item}
                    {i.quantity ? <span className="text-xs"> · {i.quantity}</span> : null}
                    {i.calories ? <span className="text-xs"> · {i.calories} kcal</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function Field({ name, label, type = "text", min, max }: { name: string; label: string; type?: string; min?: number; max?: number }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={`diet-${name}`}>{label}</Label>
      <Input id={`diet-${name}`} name={name} type={type} min={min} max={max} required />
    </div>
  )
}