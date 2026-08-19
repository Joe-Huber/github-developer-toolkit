import { useState, useEffect } from "react";
import type { ReportResponse } from "../types/report";
import { fetchReport } from "../api/client";

export function useReport(username: string | null) {
  const [data, setData] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!username) return;
    setLoading(true);
    setError(null);
    fetchReport(username)
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [username]);

  return { data, loading, error };
}
