import { scoreTone } from "../lib/colors";

const TONE_VARS: Record<ReturnType<typeof scoreTone>, string> = {
  good: "var(--ghdtk-good)",
  warn: "var(--ghdtk-warn)",
  bad: "var(--ghdtk-bad)",
};

interface ScoreGaugeProps {
  value: number;
  size?: number;
}

export function ScoreGauge({ value, size = 96 }: ScoreGaugeProps) {
  const stroke = Math.max(4, size * 0.1);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, value));
  const fraction = clamped / 100;
  const center = size / 2;
  const tone = scoreTone(clamped);

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${Math.round(clamped)} out of 100`}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="var(--ghdtk-border)"
          strokeWidth={stroke}
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={TONE_VARS[tone]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${circumference * fraction} ${circumference}`}
          transform={`rotate(-90 ${center} ${center})`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span
          className="font-bold text-text"
          style={{ fontSize: size * 0.26 }}
        >
          {Math.round(clamped)}
        </span>
        <span className="text-muted" style={{ fontSize: size * 0.12 }}>
          /100
        </span>
      </div>
    </div>
  );
}
