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
}

export default function TradingViewChart({ data, volumeData, indicators, realtimeData }: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart instance
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
        borderColor: '#D1D5DB',
      },
    });

    chartInstanceRef.current = chart;

    // Create Candlestick Series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    candlestickSeries.setData(data);
    candlestickSeriesRef.current = candlestickSeries;

    // Indicators (Line Series) — user-controlled
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

    // Create Volume Histogram (optional)
    if (volumeData && volumeData.length > 0) {
      const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: '', // set as an overlay by setting a blank priceScaleId
      });

      chart.priceScale('').applyOptions({
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      });

      volumeSeries.setData(volumeData as any);
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
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove();
      }
    };
  }, [data, volumeData, indicators]);

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
