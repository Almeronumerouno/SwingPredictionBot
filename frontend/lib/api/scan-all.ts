import { apiFetch } from "./client";

export async function triggerScrapeAll(source?: "yahoo" | "idx", date?: string): Promise<{
  status: string;
  message: string;
  stats: { gainers: number; gorengan: number; ready_to_fly: number; ready_almost?: number };
}> {
  const params = new URLSearchParams();
  if (source) params.set("source", source);
  if (date) params.set("date", date);
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiFetch(`/scrape/all${query}`, {
    method: "POST",
  });
}


