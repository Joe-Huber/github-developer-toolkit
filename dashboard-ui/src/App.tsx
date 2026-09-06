import { useState, useEffect } from "react";
import { useReport } from "./hooks/useReport";
import { Dashboard } from "./components/Dashboard";
import { ThemeToggle } from "./components/ThemeToggle";
import { ExternalLinkIcon, SearchIcon } from "./components/icons";
import { DIMENSION_ANALYSES, DIMENSION_LABELS, ANALYSIS_LABELS } from "./lib/dimensions";
import type { DimensionId } from "./types/report";

const DEMO_PROFILES = ["octocat", "torvalds", "gaearon"];

const SCORED_DIMENSIONS: DimensionId[] = [
  "presence",
  "code_quality",
  "activity",
  "engagement",
  "open_source",
  "consistency",
  "contribution",
  "visibility",
];

function getQueryParam(name: string): string | null {
  return new URLSearchParams(window.location.search).get(name);
}

function setQueryParams(updates: Record<string, string | null>) {
  const url = new URL(window.location.href);
  for (const [k, v] of Object.entries(updates)) {
    if (v === null) url.searchParams.delete(k);
    else url.searchParams.set(k, v);
  }
  window.history.replaceState(null, "", url.toString());
}

function dimensionAnalyses(dim: DimensionId): string[] {
  return DIMENSION_ANALYSES[dim].map((key) => ANALYSIS_LABELS[key]);
}

function App() {
  const [username, setUsername] = useState(() => getQueryParam("user") ?? "");
  const [activeUser, setActiveUser] = useState<string | null>(() => {
    const user = getQueryParam("user");
    return user?.trim() || null;
  });
  const [activeTab, setActiveTab] = useState<string>(() => getQueryParam("tab") ?? "overview");
  const { data, loading, error } = useReport(activeUser);

  useEffect(() => {
    if (activeUser) setQueryParams({ user: activeUser, tab: activeTab });
  }, [activeUser, activeTab]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = username.trim();
    if (trimmed) {
      setActiveTab("overview");
      setActiveUser(trimmed);
      setQueryParams({ user: trimmed, tab: "overview" });
    }
  };

  const handleBackToSearch = () => {
    setActiveUser(null);
    setQueryParams({ user: null, tab: null });
  };

  if (data) {
    return (
      <Dashboard
        report={data}
        initialTab={activeTab}
        onTabChange={setActiveTab}
        onBack={handleBackToSearch}
      />
    );
  }

  return (
    <div className="min-h-screen relative">
      <div className="absolute top-4 right-4 z-10">
        <ThemeToggle />
      </div>

      <main className="max-w-3xl mx-auto px-4 py-16">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-text mb-3">ghdtk dashboard</h1>
          <p className="text-muted text-lg">
            Explore any GitHub developer's profile as a set of scored dimensions — presence,
            code quality, activity, and more.
          </p>
        </div>

        <section aria-label="Search">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <div className="relative flex-1">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted/60" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. octocat"
                className="w-full bg-panel border border-border rounded-lg pl-9 pr-3 py-2.5 text-text text-sm placeholder:text-muted/50 focus:outline-none focus:border-accent"
              />
            </div>
            <button
              type="submit"
              disabled={!username.trim() || loading}
              className="bg-accent text-bg px-5 py-2.5 rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-40"
            >
              {loading ? "Analyzing..." : "Analyze"}
            </button>
          </form>

          <div className="mt-4 flex items-center justify-center gap-2 text-sm flex-wrap">
            <span className="text-muted">Try:</span>
            {DEMO_PROFILES.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => {
                  setUsername(name);
                  setActiveTab("overview");
                  setActiveUser(name);
                  setQueryParams({ user: name, tab: "overview" });
                }}
                className="rounded-full bg-panel border border-border px-3 py-1 text-accent hover:border-accent hover:underline"
              >
                {name}
              </button>
            ))}
          </div>
        </section>

        {loading && (
          <div
            role="status"
            aria-label="Loading"
            className="mt-6 text-center text-muted text-sm"
          >
            <div
              aria-hidden="true"
              className="inline-block animate-spin rounded-full h-4 w-4 border-2 border-accent border-t-transparent mr-2"
            />
            Fetching profile data...
          </div>
        )}

        {error && (
          <div className="mt-6 bg-bad/10 border border-bad/30 rounded-lg p-3 text-bad text-sm">
            {error}
          </div>
        )}

        <section aria-labelledby="dimensions-heading" className="mt-12">
          <h2 id="dimensions-heading" className="text-sm font-semibold text-muted uppercase tracking-wide mb-4">
            What we score
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {SCORED_DIMENSIONS.map((dim) => (
              <div key={dim} className="bg-panel border border-border rounded-lg p-4">
                <h3 className="text-sm font-semibold text-text">{DIMENSION_LABELS[dim]}</h3>
                <p className="text-xs text-muted mt-1">
                  {dimensionAnalyses(dim).join(" · ")}
                </p>
              </div>
            ))}
          </div>
        </section>

        <p className="mt-10 text-center text-xs text-muted">
          Analyzed from public GitHub data.{" "}
          <a
            href="https://github.com/Joe-Huber/github-developer-toolkit"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-accent hover:underline"
          >
            Learn more <ExternalLinkIcon className="h-3 w-3" />
          </a>
        </p>
      </main>
    </div>
  );
}

export default App;
