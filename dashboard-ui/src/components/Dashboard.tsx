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
          {sidebarOpen ? "\u2715" : "\u2630"}
        </button>
        <h1 className="text-lg font-semibold text-accent">ghdtk</h1>
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
              className="text-xs text-muted hover:text-text transition-colors"
              title="Back to search"
            >
              &larr; new
            </button>
          )}
        </div>
        <h2 className="text-sm font-medium text-muted uppercase tracking-wider mb-3">
          @{profile.username}
        </h2>
        <nav className="space-y-1">
          {DIMENSIONS.map((dim) => (
            <button
              key={dim.id}
              onClick={() => switchTab(dim.id)}
              className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                activeTab === dim.id
                  ? "bg-accent/15 text-accent"
                  : "text-muted hover:text-text hover:bg-border/30"
              }`}
            >
              {dim.label}
            </button>
          ))}
        </nav>
        <div className="mt-6 pt-4 border-t border-border text-xs text-muted">
          Generated: {new Date(report.generated_at).toLocaleDateString()}
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
