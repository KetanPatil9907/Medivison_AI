"use client"

import { useState } from "react"
import { Phone, Plus, Trash2, UserRound } from "lucide-react"

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
import { toast } from "@/components/ui/toast"
import { mutate, useApi } from "@/hooks/use-api"
import { titleCase } from "@/lib/utils"

interface ProfileData {
  profile: {
    id: number
    date_of_birth: string | null
    age: number | null
    gender: string | null
    blood_group: string | null
    height_cm: number | null
    weight_kg: number | null
    allergies: string | null
    chronic_conditions: string | null
    family_history: string | null
    city: string | null
    state: string | null
    country: string | null
    activity_level: string | null
    dietary_preference: string | null
    health_goal: string | null
  }
  user: { id: number; full_name: string; email: string; phone: string | null }
}

interface Contact {
  id: number
  name: string
  phone: string
  relation: string
  is_primary: boolean
}

export default function ProfilePage() {
  const { data: profile, loading, error, refetch } = useApi<ProfileData>("/patients/me/profile")
  const { data: contacts, refetch: refetchContacts } = useApi<Contact[]>("/patients/me/emergency-contacts")
  const [saving, setSaving] = useState(false)
  const [adding, setAdding] = useState(false)

  async function saveProfile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setSaving(true)
    try {
      await mutate("/patients/me/profile", {
        method: "PUT",
        body: {
          age: fd.get("age") ? Number(fd.get("age")) || null : null,
          gender: fd.get("gender") || null,
          blood_group: fd.get("blood_group") || null,
          height_cm: fd.get("height_cm") ? Number(fd.get("height_cm")) || null : null,
          weight_kg: fd.get("weight_kg") ? Number(fd.get("weight_kg")) || null : null,
          allergies: fd.get("allergies") || null,
          chronic_conditions: fd.get("chronic_conditions") || null,
          family_history: fd.get("family_history") || null,
          city: fd.get("city") || null,
          state: fd.get("state") || null,
          country: fd.get("country") || null,
          activity_level: fd.get("activity_level") || null,
          dietary_preference: fd.get("dietary_preference") || null,
          health_goal: fd.get("health_goal") || null,
        },
      })
      toast.success("Profile updated")
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed")
    } finally {
      setSaving(false)
    }
  }

  async function addContact(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setAdding(true)
    try {
      await mutate("/patients/me/emergency-contacts", {
        method: "POST",
        body: {
          name: fd.get("name"),
          phone: fd.get("phone"),
          relation: fd.get("relation"),
          is_primary: fd.get("is_primary") === "on",
        },
      })
      toast.success("Contact added")
      e.currentTarget.reset()
      refetchContacts()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add contact")
    } finally {
      setAdding(false)
    }
  }

  async function removeContact(id: number) {
    try {
      await mutate(`/patients/me/emergency-contacts/${id}`, { method: "DELETE" })
      toast.success("Contact removed")
      refetchContacts()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not remove contact")
    }
  }

  const p = profile?.profile

  return (
    <div className="space-y-6">
      <PageHeader title="My profile" description="Keep your health details up to date" />

      {error ? <Alert variant="destructive" title="Could not load profile">{error}</Alert> : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Health profile</CardTitle>
            <CardDescription>{profile?.user.full_name} · {profile?.user.email}</CardDescription>
          </CardHeader>
          <CardContent>
            {loading && !p ? <Spinner className="py-10" /> : null}
            {p ? (
              <form onSubmit={saveProfile} className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-age">Age</Label>
                    <Input id="pr-age" name="age" type="number" defaultValue={p.age ?? undefined} />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-gender">Gender</Label>
                    <Select id="pr-gender" name="gender" defaultValue={p.gender ?? ""}>
                      <option value="">—</option>
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                      <option value="Other">Other</option>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-blood">Blood group</Label>
                    <Select id="pr-blood" name="blood_group" defaultValue={p.blood_group ?? ""}>
                      <option value="">—</option>
                      {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((bg) => (
                        <option key={bg} value={bg}>{bg}</option>
                      ))}
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-height">Height (cm)</Label>
                    <Input id="pr-height" name="height_cm" type="number" step="any" defaultValue={p.height_cm ?? undefined} />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-weight">Weight (kg)</Label>
                    <Input id="pr-weight" name="weight_kg" type="number" step="any" defaultValue={p.weight_kg ?? undefined} />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-goal">Health goal</Label>
                    <Input id="pr-goal" name="health_goal" defaultValue={p.health_goal ?? undefined} placeholder="e.g. better stamina" />
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-activity">Activity level</Label>
                    <Select id="pr-activity" name="activity_level" defaultValue={p.activity_level ?? ""}>
                      <option value="">—</option>
                      {["sedentary", "light", "moderate", "active", "very_active"].map((a) => (
                        <option key={a} value={a}>{titleCase(a)}</option>
                      ))}
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-diet">Dietary preference</Label>
                    <Select id="pr-diet" name="dietary_preference" defaultValue={p.dietary_preference ?? ""}>
                      <option value="">—</option>
                      <option value="vegetarian">Vegetarian</option>
                      <option value="non_vegetarian">Non vegetarian</option>
                      <option value="vegan">Vegan</option>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-allergies">Allergies</Label>
                    <Input id="pr-allergies" name="allergies" defaultValue={p.allergies ?? undefined} placeholder="Comma separated" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-chronic">Chronic conditions</Label>
                    <Input id="pr-chronic" name="chronic_conditions" defaultValue={p.chronic_conditions ?? undefined} placeholder="Comma separated" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pr-fam">Family history</Label>
                    <Input id="pr-fam" name="family_history" defaultValue={p.family_history ?? undefined} />
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <Field name="city" defaultValue={p.city ?? undefined} placeholder="City" />
                    <Field name="state" defaultValue={p.state ?? undefined} placeholder="State" />
                    <Field name="country" defaultValue={p.country ?? undefined} placeholder="Country" />
                  </div>
                </div>
                <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Save profile"}</Button>
              </form>
            ) : null}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><UserRound className="h-4 w-4" /> Emergency contacts</CardTitle>
            </CardHeader>
            <CardContent>
              {contacts && contacts.length === 0 ? <EmptyState title="No contacts yet" /> : null}
              {contacts && contacts.length > 0 ? (
                <ul className="divide-y">
                  {contacts.map((c) => (
                    <li key={c.id} className="flex items-center justify-between gap-2 py-2.5">
                      <div className="flex min-w-0 items-center gap-2">
                        <Phone className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <div className="min-w-0">
                          <p className="flex items-center gap-1.5 text-sm font-medium">
                            {c.name}
                            {c.is_primary ? <Badge variant="success">Primary</Badge> : null}
                          </p>
                          <p className="text-xs text-muted-foreground">{c.relation} · {c.phone}</p>
                        </div>
                      </div>
                      <Button size="icon" variant="ghost" onClick={() => removeContact(c.id)} aria-label="Remove">
                        <Trash2 className="h-4 w-4 text-rose-600" />
                      </Button>
                    </li>
                  ))}
                </ul>
              ) : null}

              <form onSubmit={addContact} className="mt-4 space-y-3 border-t pt-4">
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="ec-name">Name</Label>
                    <Input id="ec-name" name="name" required />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="ec-phone">Phone</Label>
                    <Input id="ec-phone" name="phone" required />
                  </div>
                </div>
                <div className="grid grid-cols-2 items-end gap-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="ec-relation">Relation</Label>
                    <Input id="ec-relation" name="relation" placeholder="e.g. spouse" required />
                  </div>
                  <label className="flex items-center gap-2 pb-2 text-sm">
                    <input type="checkbox" name="is_primary" className="h-4 w-4 rounded border-border" />
                    Primary
                  </label>
                </div>
                <Button type="submit" variant="outline" size="sm" disabled={adding}>
                  <Plus className="h-4 w-4" /> {adding ? "Adding…" : "Add contact"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function Field({ name, defaultValue, placeholder }: { name: string; defaultValue?: string; placeholder?: string }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={`pr-${name}`} className="capitalize">{name}</Label>
      <Input id={`pr-${name}`} name={name} defaultValue={defaultValue} placeholder={placeholder} />
    </div>
  )
}