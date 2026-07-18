import { apiFetch } from "./client";
import type { AnalisisResponse } from "@/types/api";

export async function fetchAnalisis(kode: string): Promise<AnalisisResponse> {
  return apiFetch<AnalisisResponse>(`/api/analisis/${kode}`);
}
