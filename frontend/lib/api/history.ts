import { apiFetch } from "./client";
import type { PriceHistoryResponse } from "@/types/api";

export async function fetchHistory(kode: string, days?: number): Promise<PriceHistoryResponse> {
  const params = days ? `?days=${days}` : "";
  return apiFetch<PriceHistoryResponse>(`/api/history/${kode}${params}`);
}
