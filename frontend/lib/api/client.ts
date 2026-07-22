// Allow API_BASE_URL or NEXT_PUBLIC_API_BASE_URL to be set with or without a
// trailing /api prefix.  NEXT_PUBLIC_ prefix is needed for client components
// (browser).  Server components can use either.
const RAW_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL
  || process.env.API_BASE_URL
  || "http://localhost:8000";
const BASE_URL = RAW_BASE_URL.replace(/\/api\/?$/, "");

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    next: { revalidate: 0 },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  return res.json();
}
