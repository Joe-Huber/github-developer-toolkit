import { useState, useEffect } from "react";
import type { ReportResponse } from "../types/report";
import { fetchReport } from "../api/client";

export function useReport(username: string | null) {
  const [data, setData] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    if (!username) return;
    setLoading(true);
    fetchReport(username, controller.signal)
      .then((report) => {
        if (!controller.signal.aborted) setData(report);
      })
      .catch((err: Error) => {
        if (!controller.signal.aborted) setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [username]);

  return { data, loading, error };
}
