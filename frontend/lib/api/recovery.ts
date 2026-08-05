import { apiFetch } from "./client";
import type { RecoveryResponse } from "@/types/api";

export async function fetchRecovery(kode: string, dropPct?: number, date?: string): Promise<RecoveryResponse> {
  const params = new URLSearchParams();
  if (dropPct) params.set("drop_pct", dropPct.toString());
  if (date) params.set("date", date);
  const qs = params.toString();
  return apiFetch<RecoveryResponse>(`/recovery/${kode}${qs ? `?${qs}` : ""}`);
}
