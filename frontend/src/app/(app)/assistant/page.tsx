"use client"

import { useEffect, useRef, useState } from "react"
import { Bot, RotateCcw, Send, ShieldAlert, User } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"

interface QuickReplies {
  quick_replies: { text: string; intent: string }[]
  disclaimer: string
}

interface ChatReply {
  reply: string
  source: string
  model: string
  intent?: string
  is_emergency: boolean
  quick_replies?: { text: string; intent: string }[]
  disclaimer?: string
}

interface Message {
  role: "user" | "assistant"
  content: string
  isEmergency?: boolean
  fallbackReplies?: { text: string; intent: string }[]
}

export default function AssistantPage() {
  const { data: quick } = useApi<QuickReplies>("/chat/quick-replies")
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, sending])

  async function send(text?: string) {
    const message = (text ?? input).trim()
    if (!message || sending) return
    setInput("")
    setMessages((prev) => [...prev, { role: "user", content: message }])
    setSending(true)
    try {
      const r = await mutate<ChatReply>("/chat", {
        method: "POST",
        body: { message, context: {} },
      })
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: r.reply, isEmergency: r.is_emergency, fallbackReplies: r.quick_replies },
      ])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No reply received")
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI assistant"
        description="Ask about your health, medications, diet, and more"
        actions={
          <Button variant="outline" onClick={() => setMessages([])}>
            <RotateCcw className="h-4 w-4" /> Clear
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Bot className="h-4 w-4" />
            </span>
            MediVision Assistant
          </CardTitle>
          <CardDescription>{quick?.disclaimer}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-[52vh] flex-col rounded-lg border">
            <div className="flex-1 space-y-4 overflow-y-auto p-4">
              {messages.length === 0 ? (
                <EmptyState title="How can I help?" description="Tap a suggestion below or type your question." />
              ) : (
                messages.map((m, i) => (
                  <div key={i} className={`flex gap-2 ${m.role === "user" ? "justify-end" : ""}`}>
                    {m.role === "assistant" ? (
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                        <Bot className="h-3.5 w-3.5" />
                      </span>
                    ) : null}
                    <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                      {m.isEmergency ? <Badge variant="danger" className="mb-1">Emergency guidance</Badge> : null}
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    </div>
                    {m.role === "user" ? (
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                        <User className="h-3.5 w-3.5" />
                      </span>
                    ) : null}
                  </div>
                ))
              )}
              {sending ? (
                <div className="flex gap-2">
                  <span className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Bot className="h-3.5 w-3.5" />
                  </span>
                  <span className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">Thinking…</span>
                </div>
              ) : null}
              <div ref={endRef} />
            </div>

            <div className="border-t p-3">
              {messages.length > 0 ? (
                <div className="mb-2 flex flex-wrap gap-2">
                  {(messages[messages.length - 1].fallbackReplies ?? quick?.quick_replies ?? [])
                    .slice(0, 4)
                    .map((q, i) => (
                      <button
                        key={i}
                        onClick={() => send(q.text)}
                        className="rounded-full border px-3 py-1 text-xs transition-colors hover:bg-muted"
                      >
                        {q.text}
                      </button>
                    ))}
                </div>
              ) : (
                <div className="mb-2 flex flex-wrap gap-2">
                  {(quick?.quick_replies ?? []).map((q, i) => (
                    <button
                      key={i}
                      onClick={() => send(q.text)}
                      className="rounded-full border px-3 py-1 text-xs transition-colors hover:bg-muted"
                    >
                      {q.text}
                    </button>
                  ))}
                </div>
              )}
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  send()
                }}
                className="flex gap-2"
              >
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  rows={1}
                  placeholder="Type your question…"
                  className="min-h-[44px] flex-1 resize-none"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      send()
                    }
                  }}
                />
                <Button type="submit" disabled={sending || !input.trim()}>
                  <Send className="h-4 w-4" />
                </Button>
              </form>
            </div>
          </div>
        </CardContent>
      </Card>

      <Alert variant="warning" title="Not a substitute for medical care">
        The assistant provides general health information only. In an emergency, call 112 or go to the nearest emergency
        department immediately.
      </Alert>
    </div>
  )
}