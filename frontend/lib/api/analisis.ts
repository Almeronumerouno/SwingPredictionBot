import { apiFetch } from "./client";
import type { AnalisisResponse } from "@/types/api";

export async function fetchAnalisis(kode: string, capital?: number, date?: string): Promise<AnalisisResponse> {
  const params = new URLSearchParams();
  if (capital) params.set("capital", capital.toString());
  if (date) params.set("date", date);
  const qs = params.toString();
  return apiFetch<AnalisisResponse>(`/analisis/${kode}${qs ? `?${qs}` : ""}`);
}
