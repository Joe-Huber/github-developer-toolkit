import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useReport } from "../hooks/useReport";
import type { ReportResponse } from "../types/report";

vi.mock("../api/client", () => ({
  fetchReport: vi.fn(),
}));

import { fetchReport } from "../api/client";

const mockedFetchReport = vi.mocked(fetchReport);

const report: ReportResponse = {
  tool_version: "0.1.0",
  generated_at: "2026-01-01T00:00:00Z",
  profile: {
    username: "octocat",
    analyzed_at: "2026-01-01T00:00:00Z",
    schema_version: 1,
    analyses: null,
    metrics: [],
    scores: [],
    overall: null,
    findings: [],
    recommendations: [],
    synthesis: null,
  },
};

describe("useReport", () => {
  beforeEach(() => {
    mockedFetchReport.mockReset();
  });

  it("clears stale data and error when username becomes null", async () => {
    mockedFetchReport.mockResolvedValue(report);

    const initialProps: { username: string | null } = { username: "octocat" };
    const { result, rerender } = renderHook(
      ({ username }: { username: string | null }) => useReport(username),
      { initialProps },
    );

    await waitFor(() => expect(result.current.data).toEqual(report));
    expect(result.current.data).not.toBeNull();

    rerender({ username: null });
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("clears data when returning to search from a stale report", async () => {
    mockedFetchReport.mockResolvedValue(report);

    const initialProps: { username: string | null } = { username: "octocat" };
    const { result, rerender } = renderHook(
      ({ username }: { username: string | null }) => useReport(username),
      { initialProps },
    );

    await waitFor(() => expect(result.current.data).toEqual(report));

    rerender({ username: null });
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("passes an abort signal and aborts the in-flight request on change", async () => {
    mockedFetchReport.mockResolvedValue(report);

    const initialProps: { username: string | null } = { username: "octocat" };
    const { rerender, unmount } = renderHook(
      ({ username }: { username: string | null }) => useReport(username),
      { initialProps },
    );

    await waitFor(() => expect(mockedFetchReport).toHaveBeenCalledTimes(1));
    const signal = mockedFetchReport.mock.calls[0][1];
    expect(signal).toBeInstanceOf(AbortSignal);
    expect(signal?.aborted).toBe(false);

    rerender({ username: "torvalds" });
    expect(signal?.aborted).toBe(true);
    unmount();
  });
});
