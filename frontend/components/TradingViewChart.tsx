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
  // Return empty string for gaps (no trading session)
  // The chart won't show a label when we return empty string
  if (!ts) return '';
  const istOffset = 5.5 * 60 * 60 * 1000;
  const ist = new Date(ts * 1000 + istOffset);
  const pad = (n: number) => String(n).padStart(2, '0');
  const h = ist.getUTCHours();
  const m = ist.getUTCMinutes();
  // Show date only at market open (9:15 AM IST)
  if (h === 9 && m === 15) return `${pad(ist.getUTCDate())}/${pad(ist.getUTCMonth() + 1)}`;
  return `${pad(h)}:${pad(m)}`;
}

// Safe formatter that ensures we never show epoch time (01 Jan '70)
// Smart formatter: shows dates for multi-day intraday, times for single-day
function safeIntradayFormatter(idx: number, indexToTime: Map<number, number>): string {
  const ts = indexToTime.get(idx);
  if (!ts || ts <= 0) return ' ';  // Return space for invalid/missing timestamps
  const istOffset = 5.5 * 60 * 60 * 1000;
  const ist = new Date(ts * 1000 + istOffset);
  const pad = (n: number) => String(n).padStart(2, '0');
  const h = ist.getUTCHours();
  const m = ist.getUTCMinutes();
  const d = ist.getUTCDate();
  const month = ist.getUTCMonth() + 1;
  const year = ist.getUTCFullYear();
  
  // Get previous timestamp to detect day changes
  const prevTs = indexToTime.get(idx - 1);
  
  // Check if this is a new day (either first candle at 9:15 or day changed from previous)
  const isNewDay = h === 9 && m === 15 || (prevTs && (() => {
    const prevIst = new Date(prevTs * 1000 + istOffset);
    return prevIst.getUTCDate() !== d;
  })());
  
  // For multi-day intraday charts, show date at start of each day
  if (isNewDay) {
    // Show "DD Mon" format for better readability (e.g., "21 Mar")
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${d} ${months[month - 1]}`;
  }
  
  // Show time for regular candles within the day
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

    // ─── Determine visible candle range (TradingView-style) ──────────────────
    // For intraday: show last 200 candles initially (allow scroll to see more)
    // For daily: show ALL candles (users can scroll/zoom to navigate)
    const INITIAL_VISIBLE_CANDLES = looksIntraday ? 200 : 99999;  // Large number = show all
    let visibleData = chartData.length > INITIAL_VISIBLE_CANDLES
      ? chartData.slice(-INITIAL_VISIBLE_CANDLES)
      : chartData;

    // For intraday, re-index visible data to start from 0 for proper time axis display
    let visibleIndexToTime: Map<number, number> | null = indexToTime;
    if (looksIntraday && chartData.length > INITIAL_VISIBLE_CANDLES) {
      const startIndex = chartData.length - INITIAL_VISIBLE_CANDLES;
      // Re-index visible data to start from 0
      visibleData = visibleData.map((bar, idx) => {
        const originalIdx = startIndex + idx;
        const realTime = indexToTime?.get(originalIdx);
        if (realTime !== undefined && visibleIndexToTime) {
          visibleIndexToTime.set(idx, realTime);
        }
        return { ...bar, time: idx as unknown as Time };
      });

      // For intraday, also slice volume data to match visible candles and re-index
      if (volData && volData.length > 0) {
        volData = volData.slice(-INITIAL_VISIBLE_CANDLES).map((v, idx) => ({
          ...v,
          time: idx as unknown as Time,
        }));
      }
    } else if (volData && volData.length > INITIAL_VISIBLE_CANDLES) {
      // For daily charts, just slice without re-indexing (rarely happens now)
      volData = volData.slice(-INITIAL_VISIBLE_CANDLES);
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
        scaleMargins: { top: 0.05, bottom: 0.05 },  // small margins only — large bottom causes negative axis labels
      },
      timeScale: {
        borderColor: '#E5E7EB',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 12,  // increased for better spacing on right
        minBarSpacing: 2, // prevent candles from getting too compressed
        fixLeftEdge: true,  // prevent scrolling past the first bar
        fixRightEdge: true, // prevent scrolling past the last bar
        ...(visibleIndexToTime
          ? { tickMarkFormatter: (idx: number) => safeIntradayFormatter(idx, visibleIndexToTime!) }
          : {}),
      },
      crosshair: {
        vertLine: { color: '#9CA3AF', width: 1, style: 2, labelVisible: false },  // hide time label on vertical line
        horzLine: { color: '#9CA3AF', width: 1, style: 2, labelVisible: true },
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
    candleSeries.setData(visibleData);
    candleRef.current = candleSeries;

    // Fit content to show visible data range with proper spacing
    chart.timeScale().fitContent();

    // Crosshair → notify parent
    chart.subscribeCrosshairMove((param) => {
      if (!onCrosshairMove) return;
      if (!param.time || !param.seriesData) { onCrosshairMove(null); return; }
      const raw = param.seriesData.get(candleSeries) as any;
      if (!raw) { onCrosshairMove(null); return; }

      const idx = param.time as number;
      const realTs = visibleIndexToTime ? visibleIndexToTime.get(idx) : (idx as number);
      const timeStr = realTs ? fmtTime(realTs, looksIntraday) : String(param.time);

      // Use visibleData for finding previous close
      const barIdx = looksIntraday ? idx : visibleData.findIndex(b => b.time === param.time);
      const prevClose = barIdx > 0 ? (visibleData[barIdx - 1].close as number) : (raw.open as number);

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

    // Indicators - slice data to match visible candles
    // For intraday, also normalize indicator times to match candle indices
    indicators?.forEach(ind => {
      let processedData = ind.data;

      // For intraday charts, normalize indicator times to match candle indices
      if (looksIntraday && indexToTime) {
        // Create a reverse map: original timestamp -> normalized index
        const timeToIndex = new Map<number, number>();
        indexToTime.forEach((origTime, idx) => {
          timeToIndex.set(origTime, idx);
        });

        // Convert indicator data to use normalized indices
        processedData = ind.data
          .map(point => {
            const origTime = point.time as number;
            const normalizedIdx = timeToIndex.get(origTime);
            if (normalizedIdx === undefined) return null;
            return { ...point, time: normalizedIdx as unknown as Time };
          })
          .filter((p): p is LineData => p !== null);

        // Re-index for visible range (same as candle re-indexing)
        if (chartData.length > INITIAL_VISIBLE_CANDLES) {
          const startIndex = chartData.length - INITIAL_VISIBLE_CANDLES;
          processedData = processedData
            .filter(p => (p.time as number) >= startIndex)
            .map(point => {
              const newIdx = (point.time as number) - startIndex;
              return { ...point, time: newIdx as unknown as Time };
            });
        }
      } else {
        // For daily charts, just slice
        processedData = processedData.length > INITIAL_VISIBLE_CANDLES
          ? processedData.slice(-INITIAL_VISIBLE_CANDLES)
          : processedData;
      }

      const line = chart.addLineSeries({
        color: ind.color,
        lineWidth: (ind.lineWidth ?? 2) as any,
        title: ind.name,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      line.setData(processedData);
    });

    // Volume - volData is already sliced and re-indexed earlier
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

      // Map time to candle using visibleData
      const timeToCandle = new Map<unknown, CandlestickData>();
      visibleData.forEach(c => timeToCandle.set(c.time, c));

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
    // IMPORTANT: use inline style for position:relative — Tailwind 'relative' class
    // gets purged in production Docker builds when used in a dynamic import,
    // causing the absolute canvas to escape and cover the page header.
    <div style={{ width: '100%', height: '100%', position: 'relative', minHeight: 0 }}>
      <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
    </div>
  );
}
