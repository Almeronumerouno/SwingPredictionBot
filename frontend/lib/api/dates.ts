import { apiFetch } from "./client";
import type { ScrapedDatesResponse } from "@/types/api";

export async function fetchScrapedDates(): Promise<ScrapedDatesResponse> {
  return apiFetch<ScrapedDatesResponse>("/scraped-dates");
}
