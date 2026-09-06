import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
} from "chart.js";
import type { TooltipItem } from "chart.js";
import { Bar } from "react-chartjs-2";
import type { ScoreBreakdown } from "../types/report";
import { cssVar, withAlpha } from "../lib/colors";

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend);

interface ChartsProps {
  breakdown: ScoreBreakdown[];
}

export function Charts({ breakdown }: ChartsProps) {
  const accent = cssVar("--ghdtk-accent", "#58a6ff");
  const border = cssVar("--ghdtk-border", "#30363d");
  const muted = cssVar("--ghdtk-muted", "#8b949e");
  const text = cssVar("--ghdtk-text", "#e6edf3");

  const barData = {
    labels: breakdown.map((b) => b.label),
    datasets: [
      {
        label: "Contribution",
        data: breakdown.map((b) => b.contribution),
        backgroundColor: withAlpha(accent, 0.6),
        borderColor: withAlpha(accent, 1),
        borderWidth: 1,
      },
    ],
  };

  const barOptions = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: "y" as const,
    scales: {
      x: {
        beginAtZero: true,
        grid: { color: withAlpha(border, 0.4) },
        ticks: { color: muted },
      },
      y: {
        grid: { display: false },
        ticks: { color: text, font: { size: 11 } },
      },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: TooltipItem<"bar">) => `${(ctx.parsed.x ?? 0).toFixed(1)}`,
        },
      },
    },
  };

  // Scale container height so bars stay readable regardless of breakdown size;
  // cap it and allow vertical scroll for very long lists.
  const minHeightRem = 16;
  const heightPx = Math.max(minHeightRem, breakdown.length * 1.5) * 16;

  return (
    <div
      className="max-h-96 overflow-y-auto"
      role="img"
      aria-label="Dimension contribution bar chart"
    >
      <div style={{ height: `${heightPx}px` }}>
        <Bar data={barData} options={barOptions} />
      </div>
    </div>
  );
}
