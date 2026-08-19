import type { ReportResponse } from "../types/report";

const BASE_URL = "/api";

export async function fetchReport(username: string): Promise<ReportResponse> {
  const resp = await fetch(`${BASE_URL}/report/${encodeURIComponent(username)}`);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(body.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function fetchHealth(): Promise<{ status: string }> {
  const resp = await fetch(`${BASE_URL}/health`);
  return resp.json();
}
