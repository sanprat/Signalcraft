'use client';

import React, { useEffect, useRef, useState } from 'react';
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
  isIntraday?: boolean;
  symbol?: string;
}

interface OhlcInfo {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  change: number;
  changePct: number;
}

/**
 * For intraday data we index bars 0,1,2,… so lightweight-charts doesn't
 * try to interpret Unix timestamps as "business-day" time values.
 * We keep a side-map (index → real Unix ts) to restore human-readable labels.
 */
function normaliseIntraday(data: CandlestickData[]): {
  normalisedData: CandlestickData[];
  indexToTime: Map<number, number>;
} {
  const indexToTime = new Map<number, number>();
  // Filter out any bars with a zero/epoch timestamp (bad data)
  const validData = data.filter(bar => (bar.time as number) > 1_000_000_000);
  const normalisedData = validData.map((bar, i) => {
    indexToTime.set(i, bar.time as number);
    return { ...bar, time: i as unknown as Time };
  });
  return { normalisedData, indexToTime };
}

function fmtNum(n: number) {
  return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Convert a Unix timestamp → display string in IST */
function fmtTime(ts: number, isIntraday: boolean): string {
  const d = new Date(ts * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');

  // IST = UTC + 5:30
  const istOffset = 5.5 * 60 * 60 * 1000;
  const ist = new Date(d.getTime() + istOffset);

  const date = `${pad(ist.getUTCDate())}/${pad(ist.getUTCMonth() + 1)}/${ist.getUTCFullYear()}`;
  if (!isIntraday) return date;
  return `${date} ${pad(ist.getUTCHours())}:${pad(ist.getUTCMinutes())}`;
}

/**
 * tickMarkFormatter for the intraday index axis.
 * Shows HH:MM for mid-session ticks; DD/MM at the first bar of each day
 * (first bar of NSE day = 09:15 IST = 03:45 UTC).
 */
function intradayTickFormatter(index: number, indexToTime: Map<number, number>): string {
  const ts = indexToTime.get(index);
  // Guard: missing or epoch timestamp (before 2010) → hide the tick label
  if (ts === undefined || ts < 1_262_300_000) return '';

  const d = new Date(ts * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');

  // Work in IST (UTC+5:30)
  const istOffset = 5.5 * 60 * 60 * 1000;
  const ist = new Date(d.getTime() + istOffset);
  const istHour = ist.getUTCHours();
  const istMin  = ist.getUTCMinutes();

  // 09:15 IST = start of NSE session → show date label
  if (istHour === 9 && istMin === 15) {
    return `${pad(ist.getUTCDate())}/${pad(ist.getUTCMonth() + 1)}`;
  }

  return `${pad(istHour)}:${pad(istMin)}`;
}

export default function TradingViewChart({
  data, volumeData, indicators, realtimeData, isIntraday, symbol,
}: ChartProps) {
  const chartContainerRef   = useRef<HTMLDivElement>(null);
  const chartInstanceRef    = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const indexToTimeRef      = useRef<Map<number, number> | null>(null);

  const [ohlc, setOhlc] = useState<OhlcInfo | null>(null);

  // ── Seed OHLC header from last bar ────────────────────────────────────────
  useEffect(() => {
    if (data.length === 0) return;
    const last = data[data.length - 1];
    const prev = data.length > 1 ? data[data.length - 2].close : last.close;
    const looksIntraday =
      isIntraday ?? (typeof last.time === 'number' && (last.time as number) > 1_000_000_000);
    const ts = typeof last.time === 'number' ? (last.time as number) : null;
    setOhlc({
      time: ts ? fmtTime(ts, looksIntraday) : String(last.time),
      open: last.open as number,
      high: last.high as number,
      low:  last.low  as number,
      close: last.close as number,
      change:    (last.close as number) - (prev as number),
      changePct: (((last.close as number) - (prev as number)) / (prev as number)) * 100,
    });
  }, [data, isIntraday]);

  // ── Build / rebuild chart ──────────────────────────────────────────────────
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const looksIntraday =
      isIntraday ??
      (data.length > 0 &&
        typeof data[0].time === 'number' &&
        (data[0].time as number) > 1_000_000_000);

    let chartData = data;
    let volData   = volumeData;
    let indexToTime: Map<number, number> | null = null;

    if (looksIntraday && data.length > 0) {
      const result = normaliseIntraday(data);
      chartData  = result.normalisedData;
      indexToTime = result.indexToTime;
      indexToTimeRef.current = indexToTime;

      if (volumeData && volumeData.length === data.length) {
        volData = volumeData.map((v, i) => ({ ...v, time: i as unknown as Time }));
      }
    }

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#ffffff' },
        textColor: '#4B5563',          // slightly softer than pure black
        fontSize: 12,
      },
      grid: {
        vertLines: { color: '#F3F4F6' },  // lighter grid → cleaner look
        horzLines: { color: '#F3F4F6' },
      },
      autoSize: true,
      rightPriceScale: {
        borderColor: '#E5E7EB',
        scaleMargins: { top: 0.05, bottom: 0.28 },  // leave room for volume (TV ~25%)
      },
      timeScale: {
        borderColor: '#E5E7EB',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5,
        barSpacing: 8,                  // breathing room between candles
        ...(indexToTime
          ? {
              tickMarkFormatter: (index: number) =>
                intradayTickFormatter(index, indexToTime!),
            }
          : {}),
      },
      crosshair: {
        vertLine: { color: '#9CA3AF', width: 1, style: 2 },
        horzLine: { color: '#9CA3AF', width: 1, style: 2 },
      },
    });

    chartInstanceRef.current = chart;

    // ── Candlestick series ───────────────────────────────────────────────────
    const candlestickSeries = chart.addCandlestickSeries({
      upColor:        '#089981',
      downColor:      '#f23645',
      borderVisible:  false,           // no border → slicker look like TV
      wickUpColor:    '#089981',
      wickDownColor:  '#f23645',
    });
    candlestickSeries.setData(chartData);
    candlestickSeriesRef.current = candlestickSeries;

    // ── Crosshair → update OHLC header ──────────────────────────────────────
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) return;
      const raw = param.seriesData.get(candlestickSeries) as any;
      if (!raw) return;

      const index   = param.time as number;
      const realTs  = indexToTime ? indexToTime.get(index) : (index as number);
      const timeStr = realTs
        ? fmtTime(realTs, looksIntraday)
        : (looksIntraday ? String(index) : String(param.time));

      const barIndex = looksIntraday
        ? index
        : chartData.findIndex(b => b.time === param.time);
      const prevClose =
        barIndex > 0
          ? (chartData[barIndex - 1].close as number)
          : (raw.open as number);

      setOhlc({
        time:      timeStr,
        open:      raw.open,
        high:      raw.high,
        low:       raw.low,
        close:     raw.close,
        change:    raw.close - prevClose,
        changePct: ((raw.close - prevClose) / prevClose) * 100,
      });
    });

    // ── Indicator overlays ───────────────────────────────────────────────────
    if (indicators && indicators.length > 0) {
      indicators.forEach(ind => {
        const lineSeries = chart.addLineSeries({
          color:      ind.color,
          lineWidth:  (ind.lineWidth || 2) as any,
          title:      ind.name,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        lineSeries.setData(ind.data);
      });
    }

    // ── Volume histogram ─────────────────────────────────────────────────────
    if (volData && volData.length > 0) {
      const volumeSeries = chart.addHistogramSeries({
        priceFormat:  { type: 'volume' },
        priceScaleId: 'volume',        // dedicated scale ID keeps it isolated
        lastValueVisible: false,
        priceLineVisible: false,
      });

      // Attach volume scale — occupies bottom 25% of the pane (TV style)
      chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.75, bottom: 0 },
        visible: false,                // hide the volume price axis (TV style)
      });

      // Colour each bar to match its candle direction
      const timeToCandle = new Map<unknown, CandlestickData>();
      chartData.forEach(c => timeToCandle.set(c.time, c));

      const coloredVol = volData.map((v: any) => {
        if (v.color) return v;
        const candle = timeToCandle.get(v.time);
        const isUp   = candle
          ? (candle.close as number) >= (candle.open as number)
          : true;
        return {
          ...v,
          color: isUp ? 'rgba(8, 153, 129, 0.5)' : 'rgba(242, 54, 69, 0.5)',
        };
      });

      volumeSeries.setData(coloredVol as any);
    }

    // autoSize: true handles resizing via an internal ResizeObserver —
    // no manual window listener needed (it would race with chart.remove()).
    return () => {
      chartInstanceRef.current?.remove();
      chartInstanceRef.current = null;
    };
  }, [data, volumeData, indicators, isIntraday]);

  // ── Live tick update ───────────────────────────────────────────────────────
  useEffect(() => {
    if (realtimeData && candlestickSeriesRef.current) {
      candlestickSeriesRef.current.update(realtimeData);
    }
  }, [realtimeData]);

  const isUp     = ohlc ? ohlc.change >= 0 : true;
  const chgColor = isUp ? '#059669' : '#ef4444';

  return (
    <div className="w-full h-full flex flex-col rounded-xl border border-gray-200 overflow-hidden shadow-sm bg-white">

      {/* ── OHLC header bar ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-3 py-2 border-b border-gray-100 text-xs font-mono bg-white flex-shrink-0 flex-wrap">
        {symbol && (
          <span className="font-bold text-gray-800 text-sm mr-1">{symbol}</span>
        )}
        {ohlc ? (
          <>
            <span className="text-gray-400 text-[11px]">{ohlc.time}</span>

            <span className="flex gap-1">
              <span className="text-gray-400">O</span>
              <span className="text-gray-700">{fmtNum(ohlc.open)}</span>
            </span>
            <span className="flex gap-1">
              <span className="text-gray-400">H</span>
              <span className="text-green-600 font-semibold">{fmtNum(ohlc.high)}</span>
            </span>
            <span className="flex gap-1">
              <span className="text-gray-400">L</span>
              <span className="text-red-500 font-semibold">{fmtNum(ohlc.low)}</span>
            </span>
            <span className="flex gap-1">
              <span className="text-gray-400">C</span>
              <span className="text-gray-800 font-semibold">{fmtNum(ohlc.close)}</span>
            </span>

            <span style={{ color: chgColor }} className="font-semibold ml-1">
              {isUp ? '+' : ''}{fmtNum(ohlc.change)}&nbsp;
              <span className="opacity-80">
                ({isUp ? '+' : ''}{ohlc.changePct.toFixed(2)}%)
              </span>
            </span>
          </>
        ) : (
          <span className="text-gray-300">Loading…</span>
        )}
      </div>

      {/* ── Chart canvas ────────────────────────────────────────────────────── */}
      <div className="flex-1 relative" style={{ minHeight: 0 }}>
        <div ref={chartContainerRef} style={{ position: 'absolute', inset: 0 }} />
      </div>
    </div>
  );
}
