export interface ScrapeResponse {
  status: string;
  count: number;
  message: string;
}

export interface MarketStatusResponse {
  is_open: boolean;
  message: string;
  current_time: string;
  suggested_source: string;
}

const BASE = () =>
  (process.env.NEXT_PUBLIC_API_BASE_URL || process.env.API_BASE_URL || "http://localhost:8000")
    .replace(/\/api\/?$/, "");

export async function fetchMarketStatus(): Promise<MarketStatusResponse> {
  const res = await fetch(`${BASE()}/market-status`);
  if (!res.ok) throw new Error("Gagal cek status pasar");
  return res.json();
}

export async function triggerScrape(source?: string): Promise<ScrapeResponse> {
  const params = source ? `?source=${source}` : "";
  const url = `${BASE()}/scrape${params}`;

  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  return res.json();
}
