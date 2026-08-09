import type { ReadyToFlyScannerResponse } from "@/types/api"

const RAW_API_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL
  || process.env.API_BASE_URL
  || "http://localhost:8000";
const API_URL = RAW_API_URL.replace(/\/api\/?$/, "")

export async function fetchReadyToFly(date?: string): Promise<ReadyToFlyScannerResponse> {
  const url = new URL(`${API_URL}/readytofly`)
  if (date) {
    url.searchParams.append("date", date)
  }

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  })

  if (!res.ok) {
    let errorDetail = "Failed to fetch ready-to-fly data"
    try {
      const errData = await res.json()
      errorDetail = errData.detail || errorDetail
    } catch {
      // Ignore JSON parse error
    }
    const err = new Error(errorDetail) as Error & { status?: number }
    err.status = res.status
    throw err
  }

  return res.json()
}

export async function triggerScrapeReadyToFly(date?: string) {
  const url = new URL(`${API_URL}/scrape/readytofly`)
  if (date) {
    url.searchParams.append("date", date)
  }

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })

  if (!res.ok) {
    let errorDetail = "Failed to trigger scan ready-to-fly"
    try {
      const errData = await res.json()
      errorDetail = errData.detail || errorDetail
    } catch {
      // Ignore JSON parse error
    }
    throw new Error(errorDetail)
  }

  return res.json()
}
