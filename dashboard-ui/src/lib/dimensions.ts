import type { DimensionId, ProfileAnalyses } from "../types/report";

export const DIMENSION_LABELS: Record<DimensionId, string> = {
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

export const DIMENSION_ANALYSES: Record<DimensionId, (keyof ProfileAnalyses)[]> = {
  presence: ["presence"],
  code_quality: ["repository_quality"],
  activity: ["repository_activity", "commits"],
  engagement: ["pull_requests", "issues"],
  documentation: ["readme"],
  open_source: ["pull_requests", "stars", "star_growth", "network"],
  consistency: ["commits", "contribution_calendar"],
  contribution: ["commits", "contribution_calendar", "pull_requests"],
  visibility: ["stars", "star_growth", "network"],
};

export const ANALYSIS_LABELS: Record<keyof ProfileAnalyses, string> = {
  presence: "Profile",
  readme: "README",
  repository_quality: "Repository Quality",
  repository_activity: "Repository Activity",
  portfolio: "Portfolio",
  stars: "Stars",
  star_growth: "Star Growth",
  network: "Follow Network",
  commits: "Commits",
  contribution_calendar: "Contribution Calendar",
  pull_requests: "Pull Requests",
  issues: "Issues",
  languages: "Languages",
  technology: "Technology",
};
