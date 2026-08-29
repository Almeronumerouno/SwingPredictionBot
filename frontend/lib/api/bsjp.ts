import type { BSJPScannerResponse } from "@/types/api"

const RAW_API_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL
  || process.env.API_BASE_URL
  || "http://localhost:8000";
const API_URL = RAW_API_URL.replace(/\/api\/?$/, "")

export async function fetchBSJP(date?: string): Promise<BSJPScannerResponse> {
  const url = new URL(`${API_URL}/bsjp`)
  if (date) {
    url.searchParams.append("date", date)
  }

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  })

  if (!res.ok) {
    let errorDetail = "Failed to fetch BSJP data"
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
