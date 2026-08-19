import type {
  DimensionId,
  DimensionScore,
  Finding,
  Recommendation,
} from "../types/report";
import { Charts } from "./Charts";
import { FindingsList } from "./FindingsList";
import { RecommendationsList } from "./RecommendationsList";

const DIMENSION_LABELS: Record<DimensionId, string> = {
  presence: "Presence",
  code_quality: "Code Quality",
  activity: "Activity",
  engagement: "Engagement",
  documentation: "Documentation",
  open_source: "Open Source",
  consistency: "Consistency",
  contribution: "Contribution",
  visibility: "Visibility",
};

interface DimensionDetailProps {
  dimension: DimensionId;
  scores: DimensionScore[];
  findings: Finding[];
  recommendations: Recommendation[];
}

export function DimensionDetail({
  dimension,
  scores,
  findings,
  recommendations,
}: DimensionDetailProps) {
  const score = scores.find((s) => s.dimension === dimension);

  return (
    <div className="space-y-6">
      <div className="bg-panel rounded-lg border border-border p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-text">
            {DIMENSION_LABELS[dimension]}
          </h2>
          {score && (
            <div className="text-3xl font-bold text-accent">
              {Math.round(score.score)}
              <span className="text-sm text-muted">/100</span>
            </div>
          )}
        </div>

        {score?.rationale && (
          <p className="text-muted text-sm mb-4">{score.rationale}</p>
        )}

        {score?.breakdown && score.breakdown.length > 0 && (
          <Charts breakdown={score.breakdown} />
        )}
      </div>

      <FindingsList findings={findings} title="Findings" />
      <RecommendationsList recommendations={recommendations} title="Recommendations" />
    </div>
  );
}
