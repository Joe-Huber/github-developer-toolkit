import type { ReactNode } from "react";
import type { ContributionCalendarAnalysis, ContributionWeekPoint } from "../types/report";

const WEEKDAY_LABELS: Record<number, string> = { 1: "Mon", 3: "Wed", 5: "Fri" };
const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const LEVEL_STYLES = [
  "bg-border/40",
  "bg-accent/25",
  "bg-accent/45",
  "bg-accent/70",
  "bg-accent",
];

function parseUtcDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function weekdayOf(value: string): number {
  return parseUtcDate(value).getUTCDay();
}

function monthOf(value: string | null): number | null {
  if (value === null) return null;
  const parsed = parseUtcDate(value);
  return parsed.getUTCMonth();
}

function contributionLevel(count: number, max: number): number {
  if (count <= 0) return 0;
  if (max <= 0) return 1;
  return Math.min(4, Math.ceil((count / max) * 4));
}

function pluralized(count: number): string {
  return count === 1 ? "contribution" : "contributions";
}

function WeekColumn({ week, max }: { week: ContributionWeekPoint; max: number }) {
  const byWeekday = new Map<number, ContributionWeekPoint["days"][number]>();
  for (const day of week.days) {
    byWeekday.set(weekdayOf(day.date), day);
  }
  const cells: ReactNode[] = [];
  for (let weekday = 0; weekday < 7; weekday += 1) {
    const day = byWeekday.get(weekday);
    if (day) {
      const level = contributionLevel(day.count, max);
      cells.push(
        <div
          key={day.date}
          role="gridcell"
          aria-label={`${day.count} ${pluralized(day.count)} on ${day.date}`}
          className={`h-3 w-3 rounded-sm ${LEVEL_STYLES[level]}`}
        >
          <span className="sr-only">{`${day.date}: ${day.count}`}</span>
        </div>,
      );
    } else {
      cells.push(<div key={`empty-${weekday}`} className="h-3 w-3" aria-hidden="true" />);
    }
  }
  return (
    <div className="flex flex-col gap-[3px]" role="presentation">
      {cells}
    </div>
  );
}

interface ContributionGraphProps {
  analysis: ContributionCalendarAnalysis | null;
}

export function ContributionGraph({ analysis }: ContributionGraphProps) {
  if (analysis === null) return null;

  const weeks = analysis.weeks ?? [];
  const max = Math.max(0, ...weeks.flatMap((week) => week.days.map((day) => day.count)));

  if (weeks.length === 0) {
    return (
      <section aria-label="Contribution graph" className="bg-panel border border-border rounded-lg p-6">
        <h3 className="text-sm font-semibold text-muted uppercase tracking-wide mb-4">
          Contributions
        </h3>
        <p className="text-sm text-muted">Contribution calendar is unavailable.</p>
      </section>
    );
  }

  const monthCells: (number | null)[] = [];
  let lastMonth: number | null = null;
  for (const week of weeks) {
    const month = monthOf(week.first_day);
    if (month !== null && month !== lastMonth) {
      monthCells.push(month);
      lastMonth = month;
    } else {
      monthCells.push(null);
    }
  }

  return (
    <section aria-label="Contribution graph" className="bg-panel border border-border rounded-lg p-6">
      <div className="flex items-baseline justify-between gap-2 mb-4">
        <h3 className="text-sm font-semibold text-muted uppercase tracking-wide">
          Contributions
        </h3>
        <span className="text-sm font-semibold text-text">
          {analysis.total_contributions?.toLocaleString("en-US") ?? "—"} total
        </span>
      </div>

      <div className="overflow-x-auto">
        <div className="inline-block min-w-0">
          <div className="flex pl-8">
            {monthCells.map((month, index) => (
              <div key={index} className="w-3 mx-[1.5px] text-[9px] text-muted leading-3 truncate">
                {month !== null ? MONTH_LABELS[month] : ""}
              </div>
            ))}
          </div>
          <div className="flex gap-[3px] mt-1" role="grid" aria-label="Daily contributions">
            <div className="mr-1 flex flex-col gap-[3px]" aria-hidden="true">
              {Array.from({ length: 7 }, (_, weekday) => (
                <div key={weekday} className="h-3 w-8 text-[9px] text-muted leading-3">
                  {WEEKDAY_LABELS[weekday] ?? ""}
                </div>
              ))}
            </div>
            {weeks.map((week, index) => (
              <WeekColumn key={week.first_day ?? index} week={week} max={max} />
            ))}
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-end gap-1 text-[10px] text-muted">
        <span>Less</span>
        {LEVEL_STYLES.map((style) => (
          <span key={style} className={`h-3 w-3 rounded-sm ${style}`} aria-hidden="true" />
        ))}
        <span>More</span>
      </div>

      {analysis.restricted_contributions ? (
        <p className="mt-3 text-xs text-muted">
          {analysis.restricted_contributions} contribution
          {analysis.restricted_contributions === 1 ? "" : "s"} hidden (private repositories).
        </p>
      ) : null}
    </section>
  );
}
