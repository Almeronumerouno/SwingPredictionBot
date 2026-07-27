import { apiFetch } from "./client";
import type { HistoryResponse } from "@/types/api";

export async function fetchHistory(kode: string, length?: number, date?: string): Promise<HistoryResponse> {
  const params = new URLSearchParams();
  if (length) params.set("length", length.toString());
  if (date) params.set("date", date);
  const qs = params.toString();
  return apiFetch<HistoryResponse>(`/history/${kode}${qs ? `?${qs}` : ""}`);
}
