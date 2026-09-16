"use client"

import { useState } from "react"
import { Download, FileText, Upload } from "lucide-react"

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
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"
import type { PaginatedData } from "@/lib/types"
import { formatDate } from "@/lib/utils"

const CATEGORIES = ["blood_report", "xray", "prescription", "document", "scan", "other"]

interface Report {
  id: number
  title: string
  category: string
  report_date: string | null
  condition: string | null
  notes: string | null
  file_name: string | null
  file_size: number | null
  download_url: string | null
  created_at: string | null
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

export default function ReportsPage() {
  const { data, loading, error, refetch } = useApi<PaginatedData<Report>>("/reports/my?page_size=100")
  const [uploading, setUploading] = useState(false)

  async function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const file = fd.get("file") as File
    if (!file || file.size === 0) {
      toast.error("Choose a file to upload")
      return
    }
    if (file.size > 15 * 1024 * 1024) {
      toast.error("File is larger than 15 MB")
      return
    }
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append("file", file)
      const title = (fd.get("title") as string) || file.name
      formData.append("title", title)
      formData.append("category", (fd.get("category") as string) || "other")
      if (fd.get("report_date")) formData.append("report_date", fd.get("report_date") as string)
      if (fd.get("condition")) formData.append("condition", fd.get("condition") as string)
      if (fd.get("notes")) formData.append("notes", fd.get("notes") as string)

      await mutate("/reports/upload", { method: "POST", formData })
      toast.success("Report uploaded")
      e.currentTarget.reset()
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploading(false)
    }
  }

  async function remove(id: number) {
    if (!confirm("Delete this report permanently?")) return
    try {
      await mutate(`/reports/${id}`, { method: "DELETE" })
      toast.success("Report deleted")
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed")
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Medical reports" description="Upload, browse, and download your records" />

      {error ? <Alert variant="destructive" title="Could not load reports">{error}</Alert> : null}

      <Card>
        <CardHeader>
          <CardTitle>Upload a report</CardTitle>
          <CardDescription>PDF, images and DICOM up to 15 MB.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={upload} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="r-title">Title</Label>
                <Input id="r-title" name="title" placeholder="e.g. CBC report — June 2026" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="r-cat">Category</Label>
                <Select id="r-cat" name="category" defaultValue="blood_report">
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>{c.replaceAll("_", " ")}</option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="r-date">Report date</Label>
                <Input id="r-date" name="report_date" type="date" defaultValue={todayStr()} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="r-cond">Condition (optional)</Label>
                <Input id="r-cond" name="condition" placeholder="e.g. diabetes, fever" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="r-notes">Notes</Label>
              <Textarea id="r-notes" name="notes" rows={2} placeholder="Any context for your doctor" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="r-file">File</Label>
              <Input id="r-file" name="file" type="file" required accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.dcm,.dicom" />
            </div>
            <Button type="submit" disabled={uploading}>
              <Upload className="h-4 w-4" /> {uploading ? "Uploading…" : "Upload report"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {loading && !data ? <Spinner className="py-10" /> : null}
      {data && data.items.length === 0 ? (
        <EmptyState title="No reports yet" description="Upload a lab result or scan to keep your records together." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data?.items.map((r) => (
            <Card key={r.id}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <FileText className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-medium">{r.title}</p>
                      <p className="text-xs text-muted-foreground">{r.file_name ?? r.category}</p>
                    </div>
                  </div>
                  <Badge variant="outline">{r.category.replaceAll("_", " ")}</Badge>
                </div>
                <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                  <span>{r.report_date ? formatDate(r.report_date) : formatDate(r.created_at)}</span>
                  <span>{r.file_size ? `${(r.file_size / 1024).toFixed(0)} KB` : ""}</span>
                </div>
                {r.condition ? <p className="mt-2 text-sm font-medium capitalize">{r.condition}</p> : null}
                {r.notes ? <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{r.notes}</p> : null}
                <div className="mt-4 flex gap-2">
                  {r.download_url ? (
                    <Button asChild size="sm" variant="outline">
                      <a href={r.download_url} target="_blank" rel="noreferrer">
                        <Download className="h-4 w-4" /> Download
                      </a>
                    </Button>
                  ) : null}
                  <Button size="sm" variant="outline" className="text-rose-600" onClick={() => remove(r.id)}>
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}