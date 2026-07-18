import { apiFetch } from "./client";
import type { AnalisisResponse } from "@/types/api";

export async function fetchAnalisis(kode: string, capital?: number): Promise<AnalisisResponse> {
  const params = capital ? `?capital=${capital}` : "";
  return apiFetch<AnalisisResponse>(`/analisis/${kode}${params}`);
}
