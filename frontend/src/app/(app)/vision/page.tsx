"use client"

import { useState } from "react"
import { History, ScanEye, Upload } from "lucide-react"

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

const MODALITIES = [
  { value: "chest_xray", label: "Chest X-ray" },
  { value: "brain_mri", label: "Brain MRI" },
  { value: "skin", label: "Skin lesion" },
  { value: "eye", label: "Eye / retina" },
  { value: "blood_smear", label: "Blood smear" },
]

interface Analysis {
  id: number
  modality: string
  prediction_label: string
  confidence: number
  class_probabilities: Record<string, number>
  model_name: string
  status: string
  is_demo: boolean
  error_message: string | null
  image_url: string | null
  grad_cam_url: string | null
  explanation: string | null
  created_at: string | null
}

const PREVIEW = new Set(["image/png", "image/jpeg"])

export default function VisionPage() {
  const { data, loading, refetch } = useApi<PaginatedData<Analysis>>("/vision/my-analyses?page_size=50")
  const [tab, setTab] = useState<"upload" | "history">("upload")
  const [modality, setModality] = useState("chest_xray")
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Analysis | null>(null)

  function onFile(f: File | null) {
    setFile(f)
    if (preview) URL.revokeObjectURL(preview)
    setPreview(f && PREVIEW.has(f.type) ? URL.createObjectURL(f) : null)
  }

  async function run(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!file) {
      toast.error("Choose an image to analyze")
      return
    }
    if (file.size > 15 * 1024 * 1024) {
      toast.error("Image is larger than 15 MB")
      return
    }
    setRunning(true)
    setResult(null)
    try {
      const fd = new FormData()
      fd.append("file", file)
      fd.append("modality", modality)
      const r = await mutate<Analysis>("/vision/analyze", { method: "POST", formData: fd })
      setResult(r)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Analysis failed")
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Vision analysis" description="AI screening for medical images — chest X-rays, MRI, skin, eye and blood" />

      <Tabs value={tab} onValueChange={(v) => setTab(v as "upload" | "history")}>
        <TabsList>
          <TabsTrigger value="upload" className="flex items-center gap-1.5"><ScanEye className="h-4 w-4" /> Analyze</TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-1.5"><History className="h-4 w-4" /> History</TabsTrigger>
        </TabsList>

        <TabsContent value="upload" className="space-y-6">
          {result ? (
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center justify-between gap-2">
                    <span>{titleCase(result.modality)} prediction</span>
                    <span className="text-3xl font-bold">{result.prediction_label}</span>
                  </CardTitle>
                  <CardDescription>
                    Confidence {Math.round(result.confidence * 100)}% · {result.model_name}
                    {result.is_demo ? " (demo heuristic)" : ""}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {result.image_url ? (
                    <img src={result.image_url} alt="Analyzed scan" className="max-h-64 rounded-lg border object-contain" />
                  ) : null}
                  {result.explanation ? <p className="text-sm text-muted-foreground">{result.explanation}</p> : null}
                  <div>
                    <p className="font-medium">Class breakdown</p>
                    <div className="mt-2 space-y-2">
                      {Object.entries(result.class_probabilities ?? {})
                        .sort((a, b) => b[1] - a[1])
                        .map(([label, p]) => (
                          <div key={label}>
                            <div className="flex items-center justify-between text-sm">
                              <span>{label}</span>
                              <span>{(p * 100).toFixed(1)}%</span>
                            </div>
                            <div className="mt-1 h-2 rounded-full bg-muted">
                              <div
                                className="h-2 rounded-full bg-sky-500"
                                style={{ width: `${Math.min(100, p * 100)}%` }}
                              />
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Alert variant="default">
                Image analysis results are screening predictions and are not a clinical diagnosis. A qualified specialist
                should confirm any finding.
              </Alert>
            </div>
          ) : (
            <form onSubmit={run} className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Upload an image</CardTitle>
                  <CardDescription>PNG or JPEG, up to 15 MB.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="modality">Scan type</Label>
                    <Select id="modality" value={modality} onChange={(e) => setModality(e.target.value)}>
                      {MODALITIES.map((m) => (
                        <option key={m.value} value={m.value}>{m.label}</option>
                      ))}
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="v-file">Image</Label>
                    <Input
                      id="v-file"
                      type="file"
                      accept=".png,.jpg,.jpeg"
                      onChange={(e) => onFile(e.target.files?.[0] ?? null)}
                      required
                    />
                  </div>
                  {preview ? <img src={preview} alt="Preview" className="max-h-48 rounded-lg border object-contain" /> : null}
                  <Button type="submit" disabled={running || !file}>
                    <Upload className="h-4 w-4" /> {running ? "Analyzing…" : "Analyze image"}
                  </Button>
                </CardContent>
              </Card>
            </form>
          )}
        </TabsContent>

        <TabsContent value="history">
          {loading ? <Spinner className="py-10" /> : null}
          {data && data.items.length === 0 ? <EmptyState title="No analyses yet" /> : null}
          {data && data.items.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {data.items.map((a) => (
                <Card key={a.id}>
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium">{titleCase(a.modality)}</p>
                        <p className="text-xs text-muted-foreground">{formatDate(a.created_at)}</p>
                      </div>
                      <Badge variant="outline">{Math.round(a.confidence * 100)}%</Badge>
                    </div>
                    <p className="mt-2 text-sm font-medium">{a.prediction_label}</p>
                    <p className="text-xs text-muted-foreground">{a.model_name}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  )
}