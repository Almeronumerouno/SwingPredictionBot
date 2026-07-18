import { apiFetch } from "./client";
import type { Gainer } from "@/types/api";

export async function fetchGainers(date?: string): Promise<Gainer[]> {
  const params = date ? `?date=${date}` : "";
  return apiFetch<Gainer[]>(`/api/gainers${params}`);
}
