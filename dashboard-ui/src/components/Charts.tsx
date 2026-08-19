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

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend);

interface ChartsProps {
  breakdown: ScoreBreakdown[];
}

export function Charts({ breakdown }: ChartsProps) {
  const barData = {
    labels: breakdown.map((b) => b.label),
    datasets: [
      {
        label: "Contribution",
        data: breakdown.map((b) => b.contribution),
        backgroundColor: "rgba(88, 166, 255, 0.6)",
        borderColor: "rgba(88, 166, 255, 1)",
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
        grid: { color: "rgba(48, 54, 61, 0.4)" },
        ticks: { color: "#8b949e" },
      },
      y: {
        grid: { display: false },
        ticks: { color: "#e6edf3", font: { size: 11 } },
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

  return (
    <div className="h-64">
      <Bar data={barData} options={barOptions} />
    </div>
  );
}
