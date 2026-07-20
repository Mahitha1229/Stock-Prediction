import { useEffect, useRef } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import { Candle } from '../api';

export default function CandlestickChart({
  candles,
}: {
  candles: Candle[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: {
          type: ColorType.Solid,
          color: 'transparent',
        },
        textColor: '#8890A0',
        fontFamily: 'IBM Plex Mono, monospace',
      },
      grid: {
        vertLines: {
          color: '#22262F',
        },
        horzLines: {
          color: '#22262F',
        },
      },
      width: containerRef.current.clientWidth,
      height: 380,
      timeScale: {
        borderColor: '#22262F',
      },
      rightPriceScale: {
        borderColor: '#22262F',
      },
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

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [candles]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: 380,
      }}
    />
  );
}