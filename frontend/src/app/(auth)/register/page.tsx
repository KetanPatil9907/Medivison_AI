"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth"

type TabKey = "patient" | "doctor"

const bloodGroups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

export default function RegisterPage() {
  const { registerPatient, registerDoctor } = useAuth()
  const router = useRouter()
  const [tab, setTab] = useState<TabKey>("patient")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [doctorDone, setDoctorDone] = useState(false)

  async function submitPatient(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    const fd = new FormData(e.currentTarget)
    const payload: Record<string, unknown> = {
      full_name: fd.get("full_name"),
      email: fd.get("email"),
      password: fd.get("password"),
      age: Number(fd.get("age")),
      gender: fd.get("gender"),
      phone: (fd.get("phone") as string) || null,
      blood_group: (fd.get("blood_group") as string) || null,
      height_cm: fd.get("height_cm") ? Number(fd.get("height_cm")) : null,
      weight_kg: fd.get("weight_kg") ? Number(fd.get("weight_kg")) : null,
      allergies: (fd.get("allergies") as string) || null,
      chronic_conditions: (fd.get("chronic_conditions") as string) || null,
      emergency_contact_name: (fd.get("emergency_contact_name") as string) || null,
      emergency_contact_phone: (fd.get("emergency_contact_phone") as string) || null,
      emergency_contact_relation: (fd.get("emergency_contact_relation") as string) || null,
    }
    try {
      await registerPatient(payload)
      toast.success("Account created — welcome!")
      router.push("/dashboard")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed")
    } finally {
      setSubmitting(false)
    }
  }

  async function submitDoctor(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    const fd = new FormData(e.currentTarget)
    const payload: Record<string, unknown> = {
      full_name: fd.get("full_name"),
      email: fd.get("email"),
      password: fd.get("password"),
      phone: fd.get("phone"),
      specialization: fd.get("specialization"),
      qualification: fd.get("qualification"),
      medical_registration_number: fd.get("medical_registration_number"),
      years_of_experience: Number(fd.get("years_of_experience")),
      hospital: fd.get("hospital"),
      address: fd.get("address"),
      consultation_type: fd.get("consultation_type"),
    }
    try {
      await registerDoctor(payload)
      setDoctorDone(true)
      toast.success("Application submitted for review")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed")
    } finally {
      setSubmitting(false)
    }
  }

  if (doctorDone) {
    return (
      <Alert variant="success" title="Application submitted">
        Your doctor application is now in <strong>PENDING</strong> status and has been queued for admin
        review. You will be able to sign in after it is approved.
        <div className="mt-3">
          <Button asChild variant="outline">
            <Link href="/login">Back to sign in</Link>
          </Button>
        </div>
      </Alert>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create your account</CardTitle>
        <CardDescription>Join as a patient or submit a doctor application</CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="mb-4">
            <Alert variant="destructive" title="Registration failed">
              {error}
            </Alert>
          </div>
        ) : null}

        <Tabs value={tab} onValueChange={(v) => setTab(v as TabKey)}>
          <TabsList className="w-full">
            <TabsTrigger value="patient" className="flex-1">
              Patient
            </TabsTrigger>
            <TabsTrigger value="doctor" className="flex-1">
              Doctor
            </TabsTrigger>
          </TabsList>

          <TabsContent value="patient">
            <form onSubmit={submitPatient} className="space-y-4">
              <Field formId="reg-patient" name="full_name" label="Full name" required placeholder="Jane Doe" />
              <Field formId="reg-patient" name="email" label="Email" type="email" required placeholder="you@example.com" />
              <Field
                formId="reg-patient"
                name="password"
                label="Password"
                type="password"
                required
                hint="At least 8 characters with letters and numbers."
              />
              <div className="grid grid-cols-2 gap-3">
                <Field formId="reg-patient" name="age" label="Age" type="number" min={0} max={120} required />
                <Field
                  formId="reg-patient"
                  name="gender"
                  label="Gender"
                  as="select"
                  required
                  options={["Male", "Female", "Other"]}
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <Field formId="reg-patient" name="height_cm" label="Height (cm)" type="number" min={50} max={250} />
                <Field formId="reg-patient" name="weight_kg" label="Weight (kg)" type="number" min={2} max={400} />
                <Field
                  formId="reg-patient"
                  name="blood_group"
                  label="Blood group"
                  as="select"
                  options={bloodGroups}
                />
              </div>
              <Field formId="reg-patient" name="phone" label="Phone" placeholder="+91 …" />
              <Field formId="reg-patient" name="allergies" label="Allergies" placeholder="Comma separated" />
              <Field
                formId="reg-patient"
                name="chronic_conditions"
                label="Chronic conditions"
                placeholder="Comma separated"
              />
              <div className="grid grid-cols-6 gap-3 sm:grid-cols-12">
                <div className="col-span-6 sm:col-span-5">
                  <Field formId="reg-patient" name="emergency_contact_name" label="Emergency contact" />
                </div>
                <div className="col-span-6 sm:col-span-4">
                  <Field formId="reg-patient" name="emergency_contact_phone" label="Contact phone" />
                </div>
                <div className="col-span-6 sm:col-span-3">
                  <Field formId="reg-patient" name="emergency_contact_relation" label="Relation" />
                </div>
              </div>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Creating account…" : "Create patient account"}
              </Button>
            </form>
          </TabsContent>

          <TabsContent value="doctor">
            <form onSubmit={submitDoctor} className="space-y-4">
              <Field formId="reg-doctor" name="full_name" label="Full name" required placeholder="Dr. Jane Doe" />
              <Field formId="reg-doctor" name="email" label="Email" type="email" required placeholder="you@example.com" />
              <Field
                formId="reg-doctor"
                name="password"
                label="Password"
                type="password"
                required
                hint="At least 8 characters with letters and numbers."
              />
              <div className="grid grid-cols-2 gap-3">
                <Field formId="reg-doctor" name="phone" label="Phone" required />
                <Field formId="reg-doctor" name="specialization" label="Specialization" required placeholder="Cardiology" />
              </div>
              <Field formId="reg-doctor" name="qualification" label="Qualification" required placeholder="MBBS, MD" />
              <div className="grid grid-cols-2 gap-3">
                <Field
                  formId="reg-doctor"
                  name="medical_registration_number"
                  label="Medical registration no."
                  required
                />
                <Field
                  formId="reg-doctor"
                  name="years_of_experience"
                  label="Years of experience"
                  type="number"
                  min={0}
                  max={70}
                  required
                />
              </div>
              <Field formId="reg-doctor" name="hospital" label="Hospital / Clinic" required />
              <div className="space-y-1.5">
                <Label htmlFor="reg-doctor-address">Practice address</Label>
                <Textarea id="reg-doctor-address" name="address" required rows={2} />
              </div>
              <Field
                formId="reg-doctor"
                name="consultation_type"
                label="Consultation type"
                as="select"
                required
                options={[
                  { value: "in_person", label: "In person" },
                  { value: "online", label: "Online" },
                  { value: "both", label: "Both" },
                ]}
              />
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "Submitting…" : "Submit application"}
              </Button>
            </form>
          </TabsContent>
        </Tabs>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  )
}

function Field({
  formId,
  name,
  label,
  required,
  type = "text",
  placeholder,
  hint,
  min,
  max,
  as,
  options,
}: {
  formId: string
  name: string
  label: string
  required?: boolean
  type?: string
  placeholder?: string
  hint?: string
  min?: number
  max?: number
  as?: "select"
  options?: (string | { value: string; label: string })[]
}) {
  const id = `${formId}-${name}`
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>
        {label}
        {required ? " *" : ""}
      </Label>
      {as === "select" ? (
        <Select id={id} name={name} required={required} defaultValue="">
          <option value="" disabled>
            Select…
          </option>
          {options?.map((opt) => {
            const value = typeof opt === "string" ? opt : opt.value
            const labelText = typeof opt === "string" ? opt : opt.label
            return (
              <option key={value} value={value}>
                {labelText}
              </option>
            )
          })}
        </Select>
      ) : (
        <Input id={id} name={name} type={type} required={required} placeholder={placeholder} min={min} max={max} />
      )}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}