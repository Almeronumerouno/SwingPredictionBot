import { apiFetch } from "./client";
import type { GainersResponse } from "@/types/api";

export async function fetchGainers(date?: string): Promise<GainersResponse> {
  const params = date ? `?date=${date}` : "";
  return apiFetch<GainersResponse>(`/gainers${params}`);
}
