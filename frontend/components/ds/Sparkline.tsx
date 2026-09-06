// A minimal inline trend line — not a charting library, since a 30-point
// polyline doesn't need one and every other external dependency in this
// project goes through an explicit, justified choice (see README's provider
// section). Color follows the same green/red convention as every price
// delta elsewhere in the app: trend is first-close vs last-close, not a
// separate signal.
import type { SparklinePoint } from "@/lib/api";

const VIEW_WIDTH = 100;
const VIEW_HEIGHT = 32;

export function Sparkline({ closes, width = 72, height = 24 }: { closes: SparklinePoint[]; width?: number; height?: number }) {
  if (closes.length < 2) return null;

  const values = closes.map((c) => c.close);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const positive = values[values.length - 1] >= values[0];
  const color = positive ? "var(--text-positive)" : "var(--text-negative)";

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * VIEW_WIDTH;
    const y = VIEW_HEIGHT - ((v - min) / range) * VIEW_HEIGHT;
    return [x, y] as const;
  });

  const linePath = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const fillPath = `${linePath} L${VIEW_WIDTH},${VIEW_HEIGHT} L0,${VIEW_HEIGHT} Z`;
  const gradientId = `sparkline-fill-${positive ? "up" : "down"}`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`} preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={fillPath} fill={`url(#${gradientId})`} stroke="none" />
      <path d={linePath} fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
