import { apiFetch } from "./client";
import type { HistoryResponse } from "@/types/api";

export async function fetchHistory(kode: string, length?: number): Promise<HistoryResponse> {
  const params = length ? `?length=${length}` : "";
  return apiFetch<HistoryResponse>(`/history/${kode}${params}`);
}
