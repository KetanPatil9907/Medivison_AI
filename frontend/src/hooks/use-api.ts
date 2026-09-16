"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { apiFetch } from "@/lib/api"
import { ApiError } from "@/lib/types"

interface UseApiResult<T> {
  data: T | null
  error: string | null
  loading: boolean
  refetch: () => Promise<void>
}

export function useApi<T>(path: string | null, options?: { autoFetch?: boolean }): UseApiResult<T> {
  const autoFetch = options?.autoFetch ?? true
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(autoFetch)
  const pathRef = useRef(path)

  const refetch = useCallback(async () => {
    const target = pathRef.current
    if (!target) return
    setLoading(true)
    setError(null)
    try {
      const result = await apiFetch<T>(target)
      setData(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    pathRef.current = path
    if (path && autoFetch) refetch()
  }, [path, autoFetch, refetch])

  return { data, error, loading, refetch }
}

export async function mutate<T>(path: string, options: Parameters<typeof apiFetch<T>>[1] = {}) {
  return apiFetch<T>(path, options)
}