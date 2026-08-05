"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Subscribes once to the backend's SSE stream (/api/events) and asks
 * Next.js to re-run the current route's server-side data fetch whenever a
 * call finishes processing — router.refresh() re-fetches in place, no full
 * page reload, no client-side state to keep in sync by hand. This is what
 * makes dashboards update themselves instead of only refreshing on manual
 * reload/navigation. Mounted once, globally, in the root layout.
 *
 * Native EventSource reconnects on its own after a drop — no manual retry
 * logic needed here. */
export function LiveUpdates() {
  const router = useRouter();

  useEffect(() => {
    const source = new EventSource(`${API_URL}/api/events`);
    source.addEventListener("call_status_changed", () => {
      router.refresh();
    });
    source.onerror = () => {
      // Swallow — EventSource retries the connection itself, and a
      // dashboard tab that misses one refresh isn't worth surfacing an error for.
    };
    return () => source.close();
  }, [router]);

  return null;
}
