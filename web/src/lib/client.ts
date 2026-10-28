"use client";

/** Browser call to the API through the same-origin proxy, which adds the session token. */
export async function call<T = unknown>(path: string, method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(`/api/proxy${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401) {
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    throw new Error("Please sign in.");
  }
  const data = res.status === 204 ? undefined : await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? String(data.detail) : firstError(data);
    throw new Error(detail || "Something went wrong. Please try again.");
  }
  return data as T;
}

function firstError(data: unknown): string {
  if (data && typeof data === "object") {
    for (const value of Object.values(data)) {
      if (Array.isArray(value) && value.length) return String(value[0]);
    }
  }
  return "";
}

/** A datetime-local value is read as IST, whatever the device timezone. */
export function istInputToIso(value: string): string {
  return `${value}:00+05:30`;
}

export function rupees(n: number): string {
  return `₹${n.toLocaleString("en-IN")}`;
}
