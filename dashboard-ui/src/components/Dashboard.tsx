import { useState } from "react";
import type {
  ReportResponse,
  DimensionId,
  Finding,
  Recommendation,
} from "../types/report";
import { ScoreOverview } from "./ScoreOverview";
import { DimensionDetail } from "./DimensionDetail";
import { FindingsList } from "./FindingsList";
import { RecommendationsList } from "./RecommendationsList";
import { ThemeToggle } from "./ThemeToggle";
import { BackIcon, CloseIcon, MenuIcon } from "./icons";
import { scoreTone } from "../lib/colors";

const DIMENSIONS: { id: DimensionId | "overview"; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "presence", label: "Presence" },
  { id: "code_quality", label: "Code Quality" },
  { id: "activity", label: "Activity" },
  { id: "engagement", label: "Engagement" },
  { id: "open_source", label: "Open Source" },
  { id: "consistency", label: "Consistency" },
  { id: "contribution", label: "Contribution" },
  { id: "visibility", label: "Visibility" },
];

const SCORE_PILL_CLASSES: Record<ReturnType<typeof scoreTone>, string> = {
  good: "bg-good/15 text-good",
  warn: "bg-warn/15 text-warn",
  bad: "bg-bad/15 text-bad",
};

interface DashboardProps {
  report: ReportResponse;
  initialTab?: string;
  onTabChange?: (tab: string) => void;
  onBack?: () => void;
}

export function Dashboard({
  report,
  initialTab,
  onTabChange,
  onBack,
}: DashboardProps) {
  const validTab = DIMENSIONS.some((d) => d.id === initialTab) ? (initialTab as DimensionId | "overview") : "overview";
  const [activeTab, setActiveTab] = useState<DimensionId | "overview">(validTab);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const profile = report.profile;

  const switchTab = (tab: DimensionId | "overview") => {
    setActiveTab(tab);
    onTabChange?.(tab);
    setSidebarOpen(false);
  };

  const findingsByDimension = (dim: DimensionId): Finding[] =>
    profile.findings.filter((f) => f.dimension === dim);

  const activeFindings =
    activeTab === "overview" ? [] : findingsByDimension(activeTab);

  const recommendationsForFindings = (findings: Finding[]): Recommendation[] => {
    const ids = new Set(findings.flatMap((f) => f.recommendation_ids));
    return profile.recommendations.filter((r) => ids.has(r.id));
  };

  const dimensionScore = (dim: DimensionId | "overview"): number | undefined =>
    dim === "overview"
      ? profile.overall?.overall
      : profile.scores.find((s) => s.dimension === dim)?.score;

  return (
    <div className="min-h-screen md:flex">
      {/* Mobile top bar */}
      <header className="md:hidden sticky top-0 z-20 flex items-center gap-4 bg-panel border-b border-border px-4 py-3">
        <button
          onClick={() => setSidebarOpen((open) => !open)}
          aria-label="Toggle navigation"
          aria-expanded={sidebarOpen}
          className="text-lg text-text hover:text-accent transition-colors"
        >
          {sidebarOpen ? (
            <CloseIcon className="h-5 w-5" />
          ) : (
            <MenuIcon className="h-5 w-5" />
          )}
        </button>
        <h1 className="text-lg font-semibold text-accent">ghdtk</h1>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </header>

      {/* Sidebar */}
      <aside
        className={`w-56 shrink-0 bg-panel border-r border-border p-4 md:block ${
          sidebarOpen ? "block" : "hidden"
        }`}
      >
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-lg font-semibold text-accent">ghdtk</h1>
          {onBack && (
            <button
              onClick={onBack}
              className="inline-flex items-center gap-1 text-xs text-muted hover:text-text transition-colors"
              title="Back to search"
            >
              <BackIcon className="h-3 w-3" />
              new
            </button>
          )}
        </div>
        <h2 className="text-sm font-medium text-muted uppercase tracking-wider mb-3">
          @{profile.username}
        </h2>
        <nav className="space-y-1">
          {DIMENSIONS.map((dim) => {
            const score = dimensionScore(dim.id);
            return (
              <button
                key={dim.id}
                onClick={() => switchTab(dim.id)}
                aria-label={dim.label}
                className={`w-full flex items-center justify-between px-3 py-2 rounded text-sm transition-colors ${
                  activeTab === dim.id
                    ? "bg-accent/15 text-accent"
                    : "text-muted hover:text-text hover:bg-border/30"
                }`}
              >
                <span>{dim.label}</span>
                {score !== undefined && (
                  <span
                    className={`px-1.5 py-0.5 rounded text-xs font-semibold ${SCORE_PILL_CLASSES[scoreTone(score)]}`}
                  >
                    {Math.round(score)}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="mt-6 pt-4 border-t border-border space-y-3">
          <div className="text-xs text-muted">
            Generated: {new Date(report.generated_at).toLocaleDateString()}
          </div>
          <ThemeToggle />
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-4 md:p-6 overflow-auto">
        {activeTab === "overview" ? (
          <div className="space-y-6">
            <ScoreOverview report={report} />
            <FindingsList
              findings={profile.findings}
              title="All Findings"
            />
            <RecommendationsList
              recommendations={profile.recommendations}
              title="All Recommendations"
            />
          </div>
        ) : (
          <DimensionDetail
            dimension={activeTab}
            scores={profile.scores}
            findings={activeFindings}
            recommendations={recommendationsForFindings(activeFindings)}
            analyses={profile.analyses}
          />
        )}
      </main>
    </div>
  );
}
