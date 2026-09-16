export type UserRole = "PATIENT" | "DOCTOR" | "ADMIN"
export type UserStatus = "ACTIVE" | "PENDING" | "SUSPENDED" | "REJECTED" | "DISABLED"

export interface UserPublic {
  id: number
  full_name: string
  email: string
  role: UserRole
  status: UserStatus
  preferred_language: string
  profile_image_url: string | null
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserPublic
}

export interface ApiResponse<T> {
  success: boolean
  data: T | null
  message: string | null
}

export interface ApiErrorBody {
  code: string
  message: string
  details?: unknown
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface PaginatedResponse<T> extends ApiResponse<PaginatedData<T>> {}

export class ApiError extends Error {
  code: string
  status: number
  details: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.details = details
  }
}

// ---- Domain types (shapes returned by the backend) ----

export interface PatientProfile {
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
  emergency_contact_name: string | null
  emergency_contact_phone: string | null
  emergency_contact_relation: string | null
  activity_level: string | null
  dietary_preference: string | null
  health_goal: string | null
}

export interface DashboardStats {
  [key: string]: unknown
}

export interface Appointment {
  id: number
  patient_id: number
  doctor_id: number
  family_profile_id: number | null
  scheduled_date: string
  start_time: string
  end_time: string
  duration_minutes: number
  consultation_type: string
  status: string
  reason: string | null
  symptoms_summary: string | null
  queue_position: number | null
  doctor_name?: string
  patient_name?: string
}

export interface DoctorProfile {
  id: number
  user_id: number
  specialization: string
  qualification: string
  medical_registration_number: string
  years_of_experience: number
  hospital: string
  clinic_name: string | null
  address: string
  consultation_type: string
  languages: string
  rating: number
  rating_count: number
  consultation_fee: number | null
  online_consultation_enabled: boolean
  bio: string | null
  full_name?: string
  email?: string
}

export interface HealthMetric {
  id: number
  metric_type: string
  value: number
  unit: string | null
  recorded_date: string
  notes: string | null
  source: string | null
}

export interface MedicalReport {
  id: number
  title: string
  category: string
  report_date: string | null
  condition: string | null
  notes: string | null
  file_name: string
  file_size: number
  file_type: string
  created_at: string
}

export interface Medication {
  id: number
  name: string
  dosage: string
  frequency: string
  times_per_day: number
  start_date: string
  end_date: string | null
  reminder_enabled: boolean
  refill_reminder_enabled: boolean
  instructions: string | null
  prescribed_by: string | null
  status: string
  adherence_rate: number | null
}

export interface DietPlan {
  id: number
  plan_date: string
  bmi: number | null
  bmr: number | null
  tdee: number | null
  calorie_target: number | null
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
  water_liters: number | null
  breakfast: string | null
  lunch: string | null
  dinner: string | null
  snacks: string | null
  goal: string | null
  dietary_preference: string | null
}

export interface ExercisePlan {
  id: number
  plan_start: string
  fitness_level: string
  goal: string
  weekly_plan: string | null
  medical_restrictions: string | null
  progress: string | null
}

export interface MentalWellnessEntry {
  id: number
  entry_type: string
  mood_score: number | null
  stress_level: number | null
  journal_text: string | null
  meditation_minutes: number | null
  recorded_date: string
}

export interface HealthScore {
  id: number
  score: number
  previous_score: number | null
  recorded_date: string
  breakdown: string | null
}

export interface RiskAssessment {
  id: number
  condition_type: string
  risk_level: string
  risk_percentage: number
  factors: string | null
  explanation: string | null
  recommendations: string | null
  model_name: string
  is_demo: boolean
  created_at: string
}

export interface SymptomSession {
  id: number
  selected_symptoms: string
  symptoms_text: string | null
  duration_days: number | null
  mode: string
  status: string
  created_at: string
  results?: SymptomResult[]
}

export interface SymptomResult {
  id: number
  condition_name: string
  confidence: number
  severity: string
  recommended_specialty: string | null
  emergency_flag: boolean
  advice: string | null
  model: string
}

export interface ImageAnalysis {
  id: number
  modality: string
  prediction_label: string
  confidence: number
  class_probabilities: string | null
  model_name: string
  image_key: string
  grad_cam_key: string | null
  status: string
  is_demo: boolean
  error_message: string | null
  created_at: string
}

export interface Hospital {
  id: number
  name: string
  address: string
  city: string
  phone: string | null
  latitude: number | null
  longitude: number | null
  rating: number | null
  has_emergency: boolean
  available_beds: number | null
  total_beds: number | null
  available_icu_beds: number | null
}

export interface ChatMessage {
  role: "user" | "assistant"
  content: string
  emergency?: boolean
  quick_replies?: string[]
}

export interface DoctorApplication {
  id: number
  user_id: number
  full_name?: string
  email?: string
  phone: string
  specialization: string
  qualification: string
  medical_registration_number: string
  years_of_experience: number
  hospital: string
  address: string
  consultation_type: string
  status: string
  rejection_reason: string | null
  created_at: string
}

export interface AnalyticsSnapshot {
  id: number
  scope: string
  scope_id: number | null
  snapshot_type: string
  data: string
  snapshot_date: string
}

// ---- Dashboard payloads (GET /dashboard) ----

export interface PatientDashboardPayload {
  role: "PATIENT"
  welcome: string
  health_score: { score: number | null; previous_score: number | null; recorded_date: string | null }
  overview_cards: {
    upcoming_appointments: number
    completed_appointments: number
    active_medications: number
    upcoming_reminders: number
    latest_weight: { value: number; unit: string | null; recorded_date: string } | null
  }
  upcoming_appointment: {
    date: string
    start_time: string
    doctor_full_name: string | null
    specialization: string | null
    status: string
    hospital: string | null
  } | null
  recent_timeline: { type: string; title: string; event_date: string; severity: string | null }[]
  ai_insights: {
    risk_assessment: {
      condition_type: string
      risk_level: string
      risk_percentage: number
      recorded_date: string | null
    } | null
    image_analysis: {
      modality: string
      prediction_label: string
      confidence: number
      recorded_date: string | null
    } | null
  }
  trends: Record<string, { labels: string[]; values: number[] }>
}

export interface DoctorDashboardPayload {
  role: "DOCTOR"
  today_schedule: {
    id: number
    start_time: string
    end_time: string
    patient_full_name: string | null
    status: string
    queue_position: number | null
  }[]
  stats: {
    total_patients: number
    completed_consultations: number
    upcoming: number
    pending_requests: number
  }
  upcoming_appointments: {
    id: number
    scheduled_date: string
    start_time: string
    end_time: string
    patient_full_name: string | null
    status: string
    consultation_type: string
  }[]
  recent_activity: {
    id: number
    title: string
    description: string | null
    patient_full_name: string | null
    completed_at: string | null
  }[]
}

export interface AdminDashboardPayload {
  role: "ADMIN"
  stats: {
    total_patients: number
    total_doctors: number
    pending_applications: number
    approved_doctors: number
    today_appointments: number
    total_appointments: number
    total_ai_analyses: number
    total_reports: number
  }
  user_growth: { date: string; patients: number; doctors: number }[]
  appointment_trends: { date: string; count: number }[]
  ai_usage: { date: string; symptom_checks: number; risk_assessments: number; image_analyses: number }[]
  pending_applications: {
    id: number
    user_id: number
    full_name: string | null
    specialization: string
    submitted_at: string | null
  }[]
}

export type DashboardPayload =
  | PatientDashboardPayload
  | DoctorDashboardPayload
  | AdminDashboardPayload