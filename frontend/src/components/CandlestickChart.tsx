import { useEffect, useRef } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import { Candle, Prediction, PredictionHistoryEntry } from '../api';

export default function CandlestickChart({
  candles,
  predictions = [],
  livePrediction = null,
}: {
  candles: Candle[];
  predictions?: PredictionHistoryEntry[];
  livePrediction?: Prediction | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#8890A0',
        fontFamily: 'IBM Plex Mono, monospace',
      },
      grid: {
        vertLines: { color: '#22262F' },
        horzLines: { color: '#22262F' },
      },
      width: containerRef.current.clientWidth,
      height: 380,
      timeScale: { borderColor: '#22262F' },
      rightPriceScale: { borderColor: '#22262F' },
    });

    const series = chart.addCandlestickSeries({
      upColor: '#3DD68C',
      downColor: '#FF5C5C',
      borderVisible: false,
      wickUpColor: '#3DD68C',
      wickDownColor: '#FF5C5C',
    });

    series.setData(
      candles.map((c) => ({
        time: c.date.slice(0, 10),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    // Predicted price — amber scatter point(s), one per logged prediction
    // plus the current in-flight prediction if it isn't logged yet.
    const predictedSeries = chart.addLineSeries({
      color: '#E0A52C',
      lineVisible: false,
      pointMarkersVisible: true,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    // Actual resolved price — green scatter point(s), only for predictions
    // whose target date has already passed and been resolved.
    const actualSeries = chart.addLineSeries({
      color: '#3DD68C',
      lineVisible: false,
      pointMarkersVisible: true,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    const predictedPoints = predictions
      .filter((p) => p.predicted_price != null)
      .map((p) => ({ time: p.prediction_date, value: p.predicted_price }));

    // Add the live (not-yet-logged) prediction if its date isn't already covered
    if (
      livePrediction?.status === 'done' &&
      livePrediction.predicted_price != null &&
      livePrediction.prediction_date &&
      !predictions.some((p) => p.prediction_date === livePrediction.prediction_date)
    ) {
      predictedPoints.push({
        time: livePrediction.prediction_date,
        value: livePrediction.predicted_price,
      });
    }

    // lightweight-charts requires ascending, de-duplicated time order
    predictedPoints.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));

    const actualPoints = predictions
      .filter((p) => p.status === 'resolved' && p.actual_price != null)
      .map((p) => ({ time: p.prediction_date, value: p.actual_price as number }))
      .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));

    if (predictedPoints.length > 0) predictedSeries.setData(predictedPoints);
    if (actualPoints.length > 0) actualSeries.setData(actualPoints);

    // Confidence band for the live (in-flight) prediction, drawn as two
// dashed horizontal guides on the candlestick series itself.
if (
  livePrediction?.status === 'done' &&
  livePrediction.confidence_low != null &&
  livePrediction.confidence_high != null
) {
  const upperLine = series.createPriceLine({
    price: livePrediction.confidence_high,
    color: '#E0A52C',
    lineWidth: 1,
    lineStyle: 2, // dashed
    axisLabelVisible: true,
    title: '95% upper',
  });
  const lowerLine = series.createPriceLine({
    price: livePrediction.confidence_low,
    color: '#E0A52C',
    lineWidth: 1,
    lineStyle: 2,
    axisLabelVisible: true,
    title: '95% lower',
  });

  // price lines aren't cleaned up by chart.remove() the way series are,
  // so remove them explicitly on the next effect run / unmount
  return () => {
    series.removePriceLine(upperLine);
    series.removePriceLine(lowerLine);
    window.removeEventListener('resize', handleResize);
    chart.remove();
  };
}

    chart.timeScale().fitContent();
    let upperLine: ReturnType<typeof series.createPriceLine> | null = null;
    let lowerLine: ReturnType<typeof series.createPriceLine> | null = null;

    if (
    livePrediction?.status === 'done' &&
    livePrediction.confidence_low != null &&
    livePrediction.confidence_high != null
  ) {
    upperLine = series.createPriceLine({
      price: livePrediction.confidence_high,
      color: '#E0A52C',
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: '95% upper',
    });
    lowerLine = series.createPriceLine({
      price: livePrediction.confidence_low,
      color: '#E0A52C',
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: '95% lower',
    });
  }
  
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [candles, predictions, livePrediction]);

  return (
    <div>
      <div ref={containerRef} style={{ width: '100%', height: 380 }} />
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 12, color: 'var(--text-dim)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#E0A52C', display: 'inline-block' }} />
          Predicted
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#3DD68C', display: 'inline-block' }} />
          Actual
        </span>
      </div>
    </div>
  );
}