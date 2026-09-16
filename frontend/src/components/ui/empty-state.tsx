import { Inbox } from "lucide-react"

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/30 px-6 py-12 text-center">
      <Inbox className="h-8 w-8 text-muted-foreground/50" />
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
    </div>
  )
}