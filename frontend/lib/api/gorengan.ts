import type { GorenganScannerResponse } from "@/types/api"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function fetchGorengan(date?: string): Promise<GorenganScannerResponse> {
  const url = new URL(`${API_URL}/gorengan`)
  if (date) {
    url.searchParams.append("date", date)
  }

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    // We can use Next.js caching/revalidation if needed
    // next: { revalidate: 60 }, // revalidate every minute
    cache: "no-store", // for now, always get fresh data
  })

  if (!res.ok) {
    let errorDetail = "Failed to fetch gorengan data"
    try {
      const errData = await res.json()
      errorDetail = errData.detail || errorDetail
    } catch (e) {
      // Ignore JSON parse error if response is not JSON
    }
    throw new Error(errorDetail)
  }

  return res.json()
}

export async function triggerScrapeGorengan(date?: string) {
  const url = new URL(`${API_URL}/scrape/gorengan`)
  if (date) {
    url.searchParams.append("date", date)
  }

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })

  if (!res.ok) {
    let errorDetail = "Failed to trigger scrape gorengan"
    try {
      const errData = await res.json()
      errorDetail = errData.detail || errorDetail
    } catch (e) {}
    throw new Error(errorDetail)
  }

  return res.json()
}
