import { apiFetch } from "./client";
import type { RecoveryResponse } from "@/types/api";

export async function fetchRecovery(kode: string, dropPct?: number, date?: string, refDays?: number): Promise<RecoveryResponse> {
  const params = new URLSearchParams();
  if (dropPct) params.set("drop_pct", dropPct.toString());
  if (date) params.set("date", date);
  if (refDays) params.set("ref_days", refDays.toString());
  const qs = params.toString();
  return apiFetch<RecoveryResponse>(`/recovery/${kode}${qs ? `?${qs}` : ""}`);
}
