'use client';

import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, LineData, Time } from 'lightweight-charts';

interface IndicatorConfig {
  name: string;
  data: LineData[];
  color: string;
  lineWidth?: number;
}

interface ChartProps {
  data: CandlestickData[];
  volumeData?: { time: Time; value: number; color?: string }[];
  indicators?: IndicatorConfig[];
  realtimeData?: CandlestickData;
  isIntraday?: boolean; // pass true for 1min/5min/15min charts
}

/**
 * For intraday charts, replace real Unix timestamps with sequential integer indices
 * so lightweight-charts doesn't render overnight/weekend blank spaces between sessions.
 * Returns the normalised data and a map from index → real timestamp (for the axis formatter).
 */
function normaliseIntraday(data: CandlestickData[]): {
  normalisedData: CandlestickData[];
  indexToTime: Map<number, number>;
} {
  const indexToTime = new Map<number, number>();
  const normalisedData = data.map((bar, i) => {
    indexToTime.set(i, bar.time as number);
    return { ...bar, time: i as unknown as Time };
  });
  return { normalisedData, indexToTime };
}

export default function TradingViewChart({ data, volumeData, indicators, realtimeData, isIntraday }: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Auto-detect intraday: Unix timestamps are > 1_000_000_000
    const looksIntraday = isIntraday ??
      (data.length > 0 && typeof data[0].time === 'number' && (data[0].time as number) > 1_000_000_000);

    // Normalise intraday data to sequential indices to remove session gaps
    let chartData = data;
    let volData = volumeData;
    let indexToTime: Map<number, number> | null = null;

    if (looksIntraday && data.length > 0) {
      const result = normaliseIntraday(data);
      chartData = result.normalisedData;
      indexToTime = result.indexToTime;

      // Also normalise volume data to the same indices
      if (volumeData && volumeData.length === data.length) {
        volData = volumeData.map((v, i) => ({ ...v, time: i as unknown as Time }));
      }
    }

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f3fa' },
        horzLines: { color: '#f0f3fa' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 500,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#D1D5DB',
        // Map sequential index → human-readable HH:MM label
        ...(indexToTime ? {
          tickMarkFormatter: (index: number) => {
            const ts = indexToTime!.get(index);
            if (ts === undefined) return String(index);
            const d = new Date(ts * 1000);
            const pad = (n: number) => String(n).padStart(2, '0');
            // Show date when near start of day (9:15 AM = 03:45 UTC)
            const utcHour = d.getUTCHours();
            const utcMin  = d.getUTCMinutes();
            if (utcHour === 3 && utcMin <= 20) {
              return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
            }
            return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
          },
        } : {}),
      },
    });

    chartInstanceRef.current = chart;

    // Candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    candlestickSeries.setData(chartData);
    candlestickSeriesRef.current = candlestickSeries;

    // Indicators (Line Series)
    if (indicators && indicators.length > 0) {
      indicators.forEach(ind => {
        const lineSeries = chart.addLineSeries({
          color: ind.color,
          lineWidth: (ind.lineWidth || 2) as any,
          title: ind.name,
        });
        lineSeries.setData(ind.data);
      });
    }

    // Volume histogram
    if (volData && volData.length > 0) {
      const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        priceScaleId: '',
      });
      chart.priceScale('').applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(volData as any);
    }

    // Responsive resize
    const handleResize = () => {
      if (chartContainerRef.current && chartInstanceRef.current) {
        chartInstanceRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chartInstanceRef.current?.remove();
    };
  }, [data, volumeData, indicators, isIntraday]);

  // Handle live updates
  useEffect(() => {
    if (realtimeData && candlestickSeriesRef.current) {
      candlestickSeriesRef.current.update(realtimeData);
    }
  }, [realtimeData]);

  return (
    <div
      ref={chartContainerRef}
      className="w-full rounded-xl border border-gray-200 overflow-hidden shadow-sm"
    />
  );
}
