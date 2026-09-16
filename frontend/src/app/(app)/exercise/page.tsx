"use client"

import { useState } from "react"
import { Dumbbell, History, Trophy } from "lucide-react"

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

const LEVELS = ["beginner", "intermediate", "advanced"]
const GOALS = ["general_fitness", "weight_loss", "muscle_gain", "endurance", "flexibility"]
const RESTRICTIONS = ["knee", "back", "heart", "shoulder", "none"]

interface Session {
  slot: string
  focus: string
  type: string
  duration_minutes: number
  intensity: string
  exercises: string[]
}

interface ExercisePlan {
  id: number
  plan_start: string | null
  fitness_level: string
  goal: string
  weekly_plan: Session[]
  medical_restrictions: string[]
  progress: Record<string, { completed_sessions?: number }>
  restriction_notes?: string | null
  description?: string
  created_at: string | null
}

export default function ExercisePage() {
  const { data: current, loading, error, refetch } = useApi<ExercisePlan>("/exercise/plan/current")
  const { data: plans } = useApi<PaginatedData<ExercisePlan>>("/exercise/plans?page_size=20")
  const [tab, setTab] = useState<"current" | "history">("current")
  const [level, setLevel] = useState("beginner")
  const [goal, setGoal] = useState("general_fitness")
  const [restrictions, setRestrictions] = useState<string[]>([])
  const [generating, setGenerating] = useState(false)

  const hasError = !!error

  function toggleRestriction(r: string) {
    setRestrictions((prev) =>
      prev.includes(r)
        ? prev.filter((x) => x !== r)
        : r === "none"
          ? ["none"]
          : [...prev.filter((x) => x !== "none"), r],
    )
  }

  async function generate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setGenerating(true)
    try {
      const r = await mutate<ExercisePlan>("/exercise/plan", {
        method: "POST",
        body: {
          fitness_level: level,
          goal,
          medical_restrictions: restrictions.filter((r) => r !== "none"),
        },
      })
      toast.success("Exercise plan generated")
      await refetch()
      setTab("current")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not generate plan")
    } finally {
      setGenerating(false)
    }
  }

  async function logProgress(plan: ExercisePlan) {
    const sessionValue = prompt(
      `How many sessions did you complete this week (0-7) for the ${titleCase(plan.goal)} plan?`,
      "3",
    )
    if (sessionValue === null) return
    const completedSessions = Number(sessionValue)
    if (isNaN(completedSessions) || completedSessions < 0 || completedSessions > 7) {
      toast.error("Enter a number between 0 and 7")
      return
    }
    try {
      // latest week = 1 + count of weeks already logged
      const week = 1 + Object.keys(plan.progress ?? {}).length
      await mutate(`/exercise/plans/${plan.id}/progress`, {
        method: "PUT",
        body: { week, completed_sessions: completedSessions },
      })
      toast.success("Progress saved")
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save progress")
    }
  }

  const activePlan = current ?? plans?.items[0]

  return (
    <div className="space-y-6">
      <PageHeader title="Exercise" description="Personalised weekly workout plans with progress tracking" />

      {hasError && !current ? <Alert variant="default">You don&apos;t have an exercise plan yet — generate one below.</Alert> : null}

      <Tabs value={tab} onValueChange={(v) => setTab(v as "current" | "history")}>
        <TabsList>
          <TabsTrigger value="current" className="flex items-center gap-1.5"><Dumbbell className="h-4 w-4" /> My plan</TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-1.5"><History className="h-4 w-4" /> History</TabsTrigger>
        </TabsList>

        <TabsContent value="current" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Generate a plan</CardTitle>
              <CardDescription>Tuned to your level, goal, and any medical restrictions.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={generate} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="level">Fitness level</Label>
                    <Select id="level" value={level} onChange={(e) => setLevel(e.target.value)}>
                      {LEVELS.map((l) => <option key={l} value={l}>{titleCase(l)}</option>)}
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="goal">Goal</Label>
                    <Select id="goal" value={goal} onChange={(e) => setGoal(e.target.value)}>
                      {GOALS.map((g) => <option key={g} value={g}>{titleCase(g)}</option>)}
                    </Select>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label>Medical restrictions</Label>
                  <div className="flex flex-wrap gap-2">
                    {RESTRICTIONS.map((r) => (
                      <button
                        key={r}
                        type="button"
                        onClick={() => toggleRestriction(r)}
                        className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                          restrictions.includes(r) ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted"
                        }`}
                      >
                        {r === "none" ? "None" : titleCase(r)}
                      </button>
                    ))}
                  </div>
                </div>
                <Button type="submit" disabled={generating}>{generating ? "Generating…" : "Generate plan"}</Button>
              </form>
            </CardContent>
          </Card>

          {loading && !current ? <Spinner className="py-10" /> : null}
          {activePlan ? <PlanCard plan={activePlan} onLogProgress={() => logProgress(activePlan)} /> : null}
        </TabsContent>

        <TabsContent value="history">
          {plans && plans.items.length === 0 ? <EmptyState title="No exercise plans yet" /> : null}
          {plans && plans.items.length > 0 ? (
            <div className="space-y-4">
              {plans.items.map((p) => <PlanCard key={p.id} plan={p} onLogProgress={() => logProgress(p)} />)}
            </div>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function PlanCard({ plan, onLogProgress }: { plan: ExercisePlan; onLogProgress: () => void }) {
  const totalMinutes = plan.weekly_plan.reduce((sum, s) => sum + s.duration_minutes, 0)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-2">
          <span>{titleCase(plan.goal)} plan</span>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{titleCase(plan.fitness_level)}</Badge>
            <Badge variant="outline">{totalMinutes} min/week</Badge>
            <Badge variant="info">{plan.plan_start ? `since ${formatDate(plan.plan_start)}` : ""}</Badge>
          </div>
        </CardTitle>
        <CardDescription>
          {plan.medical_restrictions.length > 0
            ? `Restrictions considered: ${plan.medical_restrictions.map(titleCase).join(", ")}`
            : "No medical restrictions applied"}
          {plan.restriction_notes ? ` · ${plan.restriction_notes}` : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {plan.weekly_plan.map((s) => (
            <div key={s.slot} className="rounded-lg border p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{s.slot}</p>
                <Badge variant={s.duration_minutes === 0 ? "secondary" : s.intensity === "high" ? "danger" : "info"}>
                  {s.duration_minutes === 0 ? "Rest" : `${s.duration_minutes} min`}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{s.focus}</p>
              <ul className="mt-1.5 space-y-0.5 text-xs text-muted-foreground">
                {s.exercises.map((ex, i) => (
                  <li key={i}>• {ex}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between rounded-lg bg-muted p-3">
          <div className="flex items-center gap-2 text-sm">
            <Trophy className="h-4 w-4 text-amber-500" />
            Progress: {Object.keys(plan.progress ?? {}).length} week(s) logged
          </div>
          <Button size="sm" variant="outline" onClick={onLogProgress}>Log this week</Button>
        </div>
      </CardContent>
    </Card>
  )
}