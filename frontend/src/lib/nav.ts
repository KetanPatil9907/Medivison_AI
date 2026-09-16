import {
  Activity,
  Brain,
  CalendarDays,
  Dumbbell,
  FileText,
  HeartPulse,
  LayoutDashboard,
  LineChart,
  MapPin,
  MessageSquare,
  Pill,
  ScanEye,
  Siren,
  Sparkles,
  Stethoscope,
  UserRound,
  UtensilsCrossed,
  Building2,
  ClipboardCheck,
  Users,
  type LucideIcon,
} from "lucide-react"

export interface NavItem {
  label: string
  href: string
  icon: LucideIcon
}

export interface NavSection {
  title: string
  items: NavItem[]
}

export const PATIENT_NAV: NavSection[] = [
  {
    title: "Overview",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { label: "Health Timeline", href: "/timeline", icon: Activity },
      { label: "My Profile", href: "/profile", icon: UserRound },
    ],
  },
  {
    title: "Clinical",
    items: [
      { label: "Appointments", href: "/appointments", icon: CalendarDays },
      { label: "Health Tracker", href: "/tracker", icon: LineChart },
      { label: "Medications", href: "/medications", icon: Pill },
      { label: "Reports", href: "/reports", icon: FileText },
    ],
  },
  {
    title: "AI Health",
    items: [
      { label: "Symptom Checker", href: "/symptoms", icon: Brain },
      { label: "Risk Assessment", href: "/risk", icon: HeartPulse },
      { label: "Vision Analysis", href: "/vision", icon: ScanEye },
      { label: "Wellness", href: "/wellness", icon: Sparkles },
      { label: "AI Assistant", href: "/assistant", icon: MessageSquare },
    ],
  },
  {
    title: "Lifestyle",
    items: [
      { label: "Diet Plans", href: "/diet", icon: UtensilsCrossed },
      { label: "Exercise Plans", href: "/exercise", icon: Dumbbell },
    ],
  },
  {
    title: "Services",
    items: [
      { label: "Healthcare Near Me", href: "/healthcare", icon: MapPin },
      { label: "Emergency", href: "/emergency", icon: Siren },
    ],
  },
]

export const DOCTOR_NAV: NavSection[] = [
  {
    title: "Overview",
    items: [{ label: "Dashboard", href: "/dashboard", icon: LayoutDashboard }],
  },
  {
    title: "Practice",
    items: [
      { label: "Appointments", href: "/appointments", icon: CalendarDays },
      { label: "Consultations", href: "/consultations", icon: Stethoscope },
      { label: "Availability", href: "/availability", icon: Activity },
    ],
  },
]

export const ADMIN_NAV: NavSection[] = [
  {
    title: "Overview",
    items: [{ label: "Dashboard", href: "/dashboard", icon: LayoutDashboard }],
  },
  {
    title: "Administration",
    items: [
      { label: "Doctor Applications", href: "/admin/applications", icon: ClipboardCheck },
      { label: "Doctors", href: "/admin/doctors", icon: Users },
      { label: "Healthcare Facilities", href: "/admin/facilities", icon: Building2 },
      { label: "Platform Analytics", href: "/admin/analytics", icon: LineChart },
    ],
  },
]

export const ROLE_NAV: Record<string, NavSection[]> = {
  PATIENT: PATIENT_NAV,
  DOCTOR: DOCTOR_NAV,
  ADMIN: ADMIN_NAV,
}

export const ROLE_LABEL: Record<string, string> = {
  PATIENT: "Patient",
  DOCTOR: "Doctor",
  ADMIN: "Administrator",
}

export { UserRound }