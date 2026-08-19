import { useState, useEffect } from "react";
import { useReport } from "./hooks/useReport";
import { Dashboard } from "./components/Dashboard";

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
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-panel border border-border rounded-lg p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold text-text mb-2">ghdtk dashboard</h1>
        <p className="text-muted text-sm mb-6">
          Enter a GitHub username to analyze and visualize their profile.
        </p>

        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="e.g. octocat"
            className="flex-1 bg-bg border border-border rounded px-3 py-2 text-text text-sm placeholder:text-muted/50 focus:outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={!username.trim() || loading}
            className="bg-accent text-bg px-4 py-2 rounded text-sm font-medium hover:opacity-90 disabled:opacity-40"
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </form>

        {loading && (
          <div className="mt-4 text-center text-muted text-sm">
            <div className="inline-block animate-spin rounded-full h-4 w-4 border-2 border-accent border-t-transparent mr-2" />
            Fetching profile data...
          </div>
        )}

        {error && (
          <div className="mt-4 bg-bad/10 border border-bad/30 rounded p-3 text-bad text-sm">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
