"use client"

const STORAGE_KEYS = {
  access: "medivision_access_token",
  refresh: "medivision_refresh_token",
  user: "medivision_user",
} as const

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://localhost:8000/api/v1"

function isBrowser(): boolean {
  return typeof window !== "undefined"
}

export const tokenStore = {
  getAccess(): string | null {
    return isBrowser() ? window.localStorage.getItem(STORAGE_KEYS.access) : null
  },
  getRefresh(): string | null {
    return isBrowser() ? window.localStorage.getItem(STORAGE_KEYS.refresh) : null
  },
  setTokens(access: string, refresh: string): void {
    if (!isBrowser()) return
    window.localStorage.setItem(STORAGE_KEYS.access, access)
    window.localStorage.setItem(STORAGE_KEYS.refresh, refresh)
  },
  setUser(user: unknown): void {
    if (!isBrowser()) return
    window.localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user))
  },
  getUser<T>(): T | null {
    if (!isBrowser()) return null
    try {
      const raw = window.localStorage.getItem(STORAGE_KEYS.user)
      return raw ? (JSON.parse(raw) as T) : null
    } catch {
      return null
    }
  },
  clear(): void {
    if (!isBrowser()) return
    window.localStorage.removeItem(STORAGE_KEYS.access)
    window.localStorage.removeItem(STORAGE_KEYS.refresh)
    window.localStorage.removeItem(STORAGE_KEYS.user)
  },
}

import { ApiError, type ApiErrorBody, type ApiResponse, type TokenResponse, type UserPublic } from "./types"

interface RequestOptions {
  method?: string
  body?: unknown
  auth?: boolean
  formData?: FormData
  skipRefresh?: boolean
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, formData, skipRefresh = false } = options
  const headers: Record<string, string> = {}
  if (!formData && body !== undefined) headers["Content-Type"] = "application/json"
  if (auth) {
    const token = tokenStore.getAccess()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
      cache: "no-store",
    })
  } catch {
    throw new ApiError(0, "network_error", "Unable to reach the server. Check your connection.")
  }

  if (response.status === 401 && auth && !skipRefresh) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      return apiFetch<T>(path, { ...options, skipRefresh: true })
    }
    tokenStore.clear()
    throw new ApiError(401, "unauthorized", "Session expired. Please log in again.")
  }

  return parseResponse<T>(response)
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = tokenStore.getRefresh()
  if (!refreshToken) return false
  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    })
    if (!response.ok) return false
    const json = (await response.json()) as ApiResponse<TokenResponse>
    if (!json.success || !json.data) return false
    tokenStore.setTokens(json.data.access_token, json.data.refresh_token)
    tokenStore.setUser(json.data.user)
    return true
  } catch {
    return false
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  let json: ApiResponse<T> | { error?: ApiErrorBody }
  try {
    json = await response.json()
  } catch {
    throw new ApiError(response.status, "invalid_response", "Received an invalid response from the server.")
  }

  if (!response.ok || !("success" in json) || json.success === false) {
    const err = (json as { error?: ApiErrorBody }).error
    throw new ApiError(
      response.status,
      err?.code ?? "request_failed",
      err?.message ?? "Request failed",
      err?.details,
    )
  }

  return (json as ApiResponse<T>).data as T
}

// ---- Auth helpers ----

export async function login(email: string, password: string): Promise<UserPublic> {
  const data = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
    auth: false,
  })
  tokenStore.setTokens(data.access_token, data.refresh_token)
  tokenStore.setUser(data.user)
  return data.user
}

export async function registerPatient(payload: Record<string, unknown>): Promise<UserPublic> {
  const data = await apiFetch<TokenResponse>("/auth/register/patient", {
    method: "POST",
    body: payload,
    auth: false,
  })
  tokenStore.setTokens(data.access_token, data.refresh_token)
  tokenStore.setUser(data.user)
  return data.user
}

export async function registerDoctor(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const data = await apiFetch<Record<string, unknown>>("/auth/register/doctor", {
    method: "POST",
    body: payload,
    auth: false,
  })
  return data
}

export function logout(): void {
  tokenStore.clear()
}

export function currentUser(): UserPublic | null {
  return tokenStore.getUser<UserPublic>()
}

export { STORAGE_KEYS }