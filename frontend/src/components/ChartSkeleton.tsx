export default function ChartSkeleton() {
  // Random-ish heights so it looks like candlestick shapes, not a flat block
  const heights = [40, 65, 50, 80, 55, 70, 45, 90, 60, 75, 50, 85, 65, 40, 70, 55, 80, 60, 45, 75]

  return (
    <div className="chart-skeleton">
      <div className="chart-skeleton__bars">
        {heights.map((h, i) => (
          <div
            key={i}
            className="chart-skeleton__bar skeleton"
            style={{ height: `${h}%` }}
          />
        ))}
      </div>
    </div>
  )
}