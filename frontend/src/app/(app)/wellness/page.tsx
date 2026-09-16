"use client"

import { useState } from "react"
import { Flame, Heart, History, Sparkles, Timer, Wind } from "lucide-react"

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
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"
import type { PaginatedData } from "@/lib/types"
import { formatDate } from "@/lib/utils"

interface WellnessEntry {
  id: number
  entry_type: string
  mood_score: number | null
  stress_level: number | null
  journal_text: string | null
  breathing_session: string | null
  meditation_minutes: number | null
  recorded_date: string | null
  created_at: string | null
}

interface Trends {
  daily: { date: string; mood: number | null; stress: number | null }[]
  weekly: { week_start: string; mood: number | null; stress: number | null }[]
  streak: number
  recommendation: string
}

export default function WellnessPage() {
  const { data: history, refetch } = useApi<PaginatedData<WellnessEntry>>("/wellness/mood?page_size=30")
  const { data: trends, refetch: refetchTrends } = useApi<Trends>("/wellness/trends")
  const [tab, setTab] = useState<"log" | "history">("log")
  const [mood, setMood] = useState(7)
  const [stress, setStress] = useState(4)
  const [journal, setJournal] = useState("")
  const [breathing, setBreathing] = useState(5)
  const [meditation, setMeditation] = useState(10)
  const [saving, setSaving] = useState<"mood" | "breathing" | "meditation" | null>(null)

  async function saveMood(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSaving("mood")
    try {
      await mutate("/wellness/mood", { method: "POST", body: { mood_score: mood, stress_level: stress, journal_text: journal || null } })
      toast.success("Mood check-in saved")
      setJournal("")
      refetch()
      refetchTrends()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save check-in")
    } finally {
      setSaving(null)
    }
  }

  async function saveBreathing(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSaving("breathing")
    try {
      await mutate("/wellness/breathing", { method: "POST", body: { duration_minutes: breathing } })
      toast.success("Breathing session recorded")
      refetch()
      refetchTrends()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save session")
    } finally {
      setSaving(null)
    }
  }

  async function saveMeditation(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSaving("meditation")
    try {
      await mutate("/wellness/meditation", { method: "POST", body: { minutes: meditation } })
      toast.success("Meditation logged")
      refetch()
      refetchTrends()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save session")
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Wellness" description="Mood tracking, breathing exercises, and mindfulness" />

      {trends && trends.recommendation ? (
        <Alert variant="success" title="Wellness insight">
          {trends.recommendation}
        </Alert>
      ) : null}

      <Tabs value={tab} onValueChange={(v) => setTab(v as "log" | "history")}>
        <TabsList>
          <TabsTrigger value="log" className="flex items-center gap-1.5"><Heart className="h-4 w-4" /> Check in</TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-1.5"><History className="h-4 w-4" /> History</TabsTrigger>
        </TabsList>

        <TabsContent value="log">
          <div className="grid gap-6 lg:grid-cols-3">
            <form onSubmit={saveMood} className="lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle>Mood check-in</CardTitle>
                  <CardDescription>How are you feeling today?</CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div>
                    <Label>Mood — {mood}/10</Label>
                    <input
                      type="range"
                      min={1}
                      max={10}
                      value={mood}
                      onChange={(e) => setMood(Number(e.target.value))}
                      className="mt-2 w-full accent-[hsl(199_89%_48%)]"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Rough</span>
                      <span>Great</span>
                    </div>
                  </div>
                  <div>
                    <Label>Stress — {stress}/10</Label>
                    <input
                      type="range"
                      min={1}
                      max={10}
                      value={stress}
                      onChange={(e) => setStress(Number(e.target.value))}
                      className="mt-2 w-full accent-rose-500"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Laid back</span>
                      <span>Overwhelmed</span>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="w-journal">Journal (optional)</Label>
                    <Textarea id="w-journal" rows={3} value={journal} onChange={(e) => setJournal(e.target.value)} placeholder="Anything on your mind?" />
                  </div>
                  <Button type="submit" disabled={saving !== null}>{saving === "mood" ? "Saving…" : "Save check-in"}</Button>
                </CardContent>
              </Card>
            </form>

            <div className="space-y-6">
              <form onSubmit={saveBreathing}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Wind className="h-4 w-4" /> Breathing</CardTitle>
                    <CardDescription>Guided calm-down exercise</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="space-y-1.5">
                      <Label htmlFor="w-breathe">Minutes</Label>
                      <Input id="w-breathe" type="number" min={1} max={60} value={breathing} onChange={(e) => setBreathing(Number(e.target.value))} />
                    </div>
                    <Button type="submit" variant="outline" className="w-full" disabled={saving !== null}>
                      {saving === "breathing" ? "Recording…" : "Complete session"}
                    </Button>
                  </CardContent>
                </Card>
              </form>

              <form onSubmit={saveMeditation}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Sparkles className="h-4 w-4" /> Meditation</CardTitle>
                    <CardDescription>Log a mindfulness session</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="space-y-1.5">
                      <Label htmlFor="w-meditate">Minutes</Label>
                      <Input id="w-meditate" type="number" min={1} max={600} value={meditation} onChange={(e) => setMeditation(Number(e.target.value))} />
                    </div>
                    <Button type="submit" variant="outline" className="w-full" disabled={saving !== null}>
                      {saving === "meditation" ? "Logging…" : "Log session"}
                    </Button>
                  </CardContent>
                </Card>
              </form>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="history">
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Check-in history</CardTitle>
              </CardHeader>
              <CardContent>
                {!history || history.items.length === 0 ? (
                  <EmptyState title="No check-ins yet" />
                ) : (
                  <ul className="divide-y">
                    {history.items.map((h) => (
                      <li key={h.id} className="py-2.5">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            {h.entry_type === "mood_journal" ? <Heart className="h-4 w-4 text-rose-500" /> : h.entry_type === "breathing" ? <Wind className="h-4 w-4 text-sky-500" /> : <Sparkles className="h-4 w-4 text-fuchsia-500" />}
                            <p className="text-sm font-medium">{h.entry_type.replaceAll("_", " ")}</p>
                          </div>
                          <div className="flex items-center gap-2">
                            {h.mood_score ? <Badge variant="info">mood {h.mood_score}</Badge> : null}
                            {h.stress_level ? <Badge variant="warning">stress {h.stress_level}</Badge> : null}
                            {h.meditation_minutes ? <Badge variant="secondary">{h.meditation_minutes} min</Badge> : null}
                            <span className="text-xs text-muted-foreground">{formatDate(h.recorded_date)}</span>
                          </div>
                        </div>
                        {h.journal_text ? <p className="mt-1 text-sm text-muted-foreground">{h.journal_text}</p> : null}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <div className="space-y-6">
              {trends ? (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Flame className="h-4 w-4" /> Stats</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Current streak</span>
                      <span className="font-semibold">{trends.streak} days</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Daily check-ins</span>
                      <span className="font-semibold">{trends.daily.filter((d) => d.mood !== null).length}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Weeks tracked</span>
                      <span className="font-semibold">{trends.weekly.length}</span>
                    </div>
                    <div className="rounded-lg bg-muted p-3 text-sm">
                      <p className="mb-1 flex items-center gap-1.5 font-medium"><Timer className="h-3.5 w-3.5" /> Recent mood trend</p>
                      {trends.weekly.slice(-4).map((w) => (
                        <div key={w.week_start} className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>Week of {formatDate(w.week_start)}</span>
                          <span>mood {w.mood?.toFixed(1) ?? "—"} · stress {w.stress?.toFixed(1) ?? "—"}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ) : <Spinner className="py-10" />}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}