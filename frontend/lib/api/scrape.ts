export interface ScrapeResponse {
  status: string;
  count: number;
  message: string;
}

export async function triggerScrape(): Promise<ScrapeResponse> {
  const BASE = process.env.NEXT_PUBLIC_API_BASE_URL
    || process.env.API_BASE_URL
    || "http://localhost:8000";
  const url = `${BASE.replace(/\/api\/?$/, "")}/scrape`;

  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  return res.json();
}
