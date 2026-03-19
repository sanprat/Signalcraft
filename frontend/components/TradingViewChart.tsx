'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  LineData,
  Time,
} from 'lightweight-charts';

export interface IndicatorConfig {
  name: string;
  data: LineData[];
  color: string;
  lineWidth?: number;
}

export interface ChartProps {
  data: CandlestickData[];
  volumeData?: { time: Time; value: number; color?: string }[];
  indicators?: IndicatorConfig[];
  realtimeData?: CandlestickData;
  isIntraday?: boolean;
  symbol?: string;
  /** Called on every crosshair move with the hovered bar's data */
  onCrosshairMove?: (bar: HoveredBar | null) => void;
}

export interface HoveredBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  change: number;
  changePct: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtTime(ts: number, isIntraday: boolean): string {
  const istOffset = 5.5 * 60 * 60 * 1000;
  const ist = new Date(ts * 1000 + istOffset);
  const pad = (n: number) => String(n).padStart(2, '0');
  const date = `${pad(ist.getUTCDate())}/${pad(ist.getUTCMonth() + 1)}/${ist.getUTCFullYear()}`;
  if (!isIntraday) return date;
  return `${date} ${pad(ist.getUTCHours())}:${pad(ist.getUTCMinutes())}`;
}

function normaliseIntraday(raw: CandlestickData[]): {
  normalisedData: CandlestickData[];
  indexToTime: Map<number, number>;
  validOriginalIndices: number[];
} {
  const indexToTime = new Map<number, number>();
  const validOriginalIndices: number[] = [];
  raw.forEach((b, i) => {
    if ((b.time as number) > 1_262_300_000) validOriginalIndices.push(i);
  });
  const normalisedData = validOriginalIndices.map((origIdx, newIdx) => {
    const bar = raw[origIdx];
    indexToTime.set(newIdx, bar.time as number);
    return { ...bar, time: newIdx as unknown as Time };
  });
  return { normalisedData, indexToTime, validOriginalIndices };
}

function intradayTickFormatter(idx: number, indexToTime: Map<number, number>): string {
  const ts = indexToTime.get(idx);
  if (!ts) return '';
  const istOffset = 5.5 * 60 * 60 * 1000;
  const ist = new Date(ts * 1000 + istOffset);
  const pad = (n: number) => String(n).padStart(2, '0');
  const h = ist.getUTCHours();
  const m = ist.getUTCMinutes();
  if (h === 9 && m === 15) return `${pad(ist.getUTCDate())}/${pad(ist.getUTCMonth() + 1)}`;
  return `${pad(h)}:${pad(m)}`;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function TradingViewChart({
  data,
  volumeData,
  indicators,
  realtimeData,
  isIntraday,
  onCrosshairMove,
}: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  useEffect(() => {
    if (!containerRef.current || !data.length) return;

    const looksIntraday =
      isIntraday ??
      (typeof data[0].time === 'number' && (data[0].time as number) > 1_000_000_000);

    let chartData: CandlestickData[] = data;
    let volData = volumeData ? [...volumeData] : undefined;
    let indexToTime: Map<number, number> | null = null;

    if (looksIntraday) {
      const { normalisedData, indexToTime: itm, validOriginalIndices } = normaliseIntraday(data);
      chartData = normalisedData;
      indexToTime = itm;

      if (volData && volData.length > 0) {
        volData = validOriginalIndices.map((origIdx, newIdx) => {
          const v = volData![origIdx] ?? volData![volData!.length - 1];
          return { ...v, time: newIdx as unknown as Time };
        });
      }
    }

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#ffffff' },
        textColor: '#4B5563',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: '#F3F4F6' },
        horzLines: { color: '#F3F4F6' },
      },
      autoSize: true,
      rightPriceScale: {
        borderColor: '#E5E7EB',
        scaleMargins: { top: 0.05, bottom: 0.25 },
      },
      timeScale: {
        borderColor: '#E5E7EB',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 8,
        ...(indexToTime
          ? { tickMarkFormatter: (idx: number) => intradayTickFormatter(idx, indexToTime!) }
          : {}),
      },
      crosshair: {
        vertLine: { color: '#9CA3AF', width: 1, style: 2 },
        horzLine: { color: '#9CA3AF', width: 1, style: 2 },
      },
    });

    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#089981',
      downColor: '#f23645',
      borderVisible: false,
      wickUpColor: '#089981',
      wickDownColor: '#f23645',
    });
    candleSeries.setData(chartData);
    candleRef.current = candleSeries;

    chart.timeScale().fitContent();

    // Crosshair → notify parent
    chart.subscribeCrosshairMove((param) => {
      if (!onCrosshairMove) return;
      if (!param.time || !param.seriesData) { onCrosshairMove(null); return; }
      const raw = param.seriesData.get(candleSeries) as any;
      if (!raw) { onCrosshairMove(null); return; }

      const idx = param.time as number;
      const realTs = indexToTime ? indexToTime.get(idx) : (idx as number);
      const timeStr = realTs ? fmtTime(realTs, looksIntraday) : String(param.time);

      const barIdx = looksIntraday ? idx : chartData.findIndex(b => b.time === param.time);
      const prevClose = barIdx > 0 ? (chartData[barIdx - 1].close as number) : (raw.open as number);

      onCrosshairMove({
        time: timeStr,
        open: raw.open,
        high: raw.high,
        low: raw.low,
        close: raw.close,
        change: raw.close - prevClose,
        changePct: ((raw.close - prevClose) / prevClose) * 100,
      });
    });

    // Indicators
    indicators?.forEach(ind => {
      const line = chart.addLineSeries({
        color: ind.color,
        lineWidth: (ind.lineWidth ?? 2) as any,
        title: ind.name,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      line.setData(ind.data);
    });

    // Volume
    if (volData?.length) {
      const volSeries = chart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: 'vol',
        lastValueVisible: false,
        priceLineVisible: false,
      });
      chart.priceScale('vol').applyOptions({
        scaleMargins: { top: 0.75, bottom: 0 },
        visible: false,
      });

      const timeToCandle = new Map<unknown, CandlestickData>();
      chartData.forEach(c => timeToCandle.set(c.time, c));

      const coloured = volData.map((v: any) => {
        if (v.color) return v;
        const candle = timeToCandle.get(v.time);
        const up = candle ? (candle.close as number) >= (candle.open as number) : true;
        return { ...v, color: up ? 'rgba(8,153,129,0.5)' : 'rgba(242,54,69,0.5)' };
      });
      volSeries.setData(coloured as any);
    }

    return () => { chart.remove(); chartRef.current = null; };
  }, [data, volumeData, indicators, isIntraday, onCrosshairMove]);

  useEffect(() => {
    if (realtimeData && candleRef.current) {
      candleRef.current.update(realtimeData);
    }
  }, [realtimeData]);

  return (
    <div className="w-full h-full relative" style={{ minHeight: 0 }}>
      <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
    </div>
  );
}
