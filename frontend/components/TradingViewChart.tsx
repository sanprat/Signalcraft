'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
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

function fmtNum(n: number) {
  return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtTime(ts: number, isIntraday: boolean): string {
  const d = new Date(ts * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  const date = `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
  if (!isIntraday) return date;
  return `${date} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function TradingViewChart({
  data, volumeData, indicators, realtimeData, isIntraday, symbol
}: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef    = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const indexToTimeRef = useRef<Map<number, number> | null>(null);

  // OHLC info shown in the header bar
  const [ohlc, setOhlc] = useState<OhlcInfo | null>(null);

  // Initialise header from last bar
  useEffect(() => {
    if (data.length === 0) return;
    const last = data[data.length - 1];
    const prev = data.length > 1 ? data[data.length - 2].close : last.close;
    const looksIntraday = isIntraday ??
      (typeof last.time === 'number' && (last.time as number) > 1_000_000_000);
    const ts = typeof last.time === 'number' ? last.time as number : null;
    setOhlc({
      time: ts ? fmtTime(ts, looksIntraday) : String(last.time),
      open: last.open as number,
      high: last.high as number,
      low: last.low as number,
      close: last.close as number,
      change: (last.close as number) - (prev as number),
      changePct: (((last.close as number) - (prev as number)) / (prev as number)) * 100,
    });
  }, [data, isIntraday]);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const looksIntraday = isIntraday ??
      (data.length > 0 && typeof data[0].time === 'number' && (data[0].time as number) > 1_000_000_000);

    let chartData = data;
    let volData = volumeData;
    let indexToTime: Map<number, number> | null = null;

    if (looksIntraday && data.length > 0) {
      const result = normaliseIntraday(data);
      chartData = result.normalisedData;
      indexToTime = result.indexToTime;
      indexToTimeRef.current = indexToTime;
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
        vertLines: { color: '#e1e3e6' },
        horzLines: { color: '#e1e3e6' },
      },
      autoSize: true,   // fills the container — no fixed height
      localization: {
        timeFormatter: (time: unknown) => {
          const index = time as number;
          if (indexToTime) {
            const realTs = indexToTime.get(index);
            if (realTs !== undefined) {
              const d = new Date(realTs * 1000);
              const pad = (n: number) => String(n).padStart(2, '0');
              return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
            }
          }
          if (typeof time === 'number') {
            const d = new Date(time * 1000);
            const pad = (n: number) => String(n).padStart(2, '0');
            return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
          }
          return String(time);
        },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#D1D5DB',
        ...(indexToTime ? {
          tickMarkFormatter: (index: number) => {
            const ts = indexToTime!.get(index);
            if (ts === undefined) return '';
            const d = new Date(ts * 1000);
            const pad = (n: number) => String(n).padStart(2, '0');
            const utcMin = d.getUTCHours() * 60 + d.getUTCMinutes();
            // 03:45 UTC = 09:15 IST (market open) → show date
            if (utcMin >= 220 && utcMin <= 230) {
              return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
            }
            return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
          },
        } : {}),
      },
    });

    chartInstanceRef.current = chart;

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#089981',
      downColor: '#f23645',
      borderVisible: true,
      wickUpColor: '#089981',
      wickDownColor: '#f23645',
      borderUpColor: '#089981',
      borderDownColor: '#f23645',
    });
    candlestickSeries.setData(chartData);
    candlestickSeriesRef.current = candlestickSeries;

    // ── Crosshair OHLC update ──────────────────────────────────────────────────
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) return;
      const raw = param.seriesData.get(candlestickSeries) as any;
      if (!raw) return;

      const index = param.time as number;
      const realTs = indexToTime ? indexToTime.get(index) : (index as number);
      const timeStr = realTs
        ? fmtTime(realTs, looksIntraday)
        : (looksIntraday ? String(index) : String(param.time));

      // Compute change vs previous bar
      const barIndex = looksIntraday ? index : chartData.findIndex(b => b.time === param.time);
      const prevClose = barIndex > 0
        ? (chartData[barIndex - 1].close as number)
        : (raw.open as number);

      setOhlc({
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

    // Volume
    if (volData && volData.length > 0) {
      const volumeSeries = chart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: '',
      });
      chart.priceScale('').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      
      const timeToCandle = new Map();
      chartData.forEach((c: any) => timeToCandle.set(c.time, c));
      
      const coloredVolData = volData.map((v: any) => {
        if (v.color) return v; // Respect already assigned color
        const candle = timeToCandle.get(v.time);
        if (candle) {
           const isUp = (candle.close as number) >= (candle.open as number);
           return { ...v, color: isUp ? 'rgba(8, 153, 129, 0.5)' : 'rgba(242, 54, 69, 0.5)' };
        }
        return v;
      });

      volumeSeries.setData(coloredVolData as any);
    }

    const handleResize = () => {
      chartInstanceRef.current?.applyOptions({
        width: chartContainerRef.current?.clientWidth ?? 0,
      });
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chartInstanceRef.current?.remove();
    };
  }, [data, volumeData, indicators, isIntraday]);

  // Live update
  useEffect(() => {
    if (realtimeData && candlestickSeriesRef.current) {
      candlestickSeriesRef.current.update(realtimeData);
    }
  }, [realtimeData]);

  const isUp = ohlc ? ohlc.change >= 0 : true;
  const chgColor = isUp ? '#059669' : '#ef4444';

  return (
    <div className="w-full h-full flex flex-col rounded-xl border border-gray-200 overflow-hidden shadow-sm bg-white">

      {/* ── TradingView-style OHLC header bar ── */}
      <div className="flex items-center gap-4 px-3 py-1.5 border-b border-gray-100 text-xs font-mono bg-gray-50 flex-shrink-0 flex-wrap">
        {symbol && (
          <span className="font-bold text-gray-700 mr-1">{symbol}</span>
        )}
        {ohlc ? (
          <>
            <span className="text-gray-400">{ohlc.time}</span>
            <span>
              <span className="text-gray-400">O </span>
              <span className="text-gray-700">{fmtNum(ohlc.open)}</span>
            </span>
            <span>
              <span className="text-gray-400">H </span>
              <span className="text-green-600 font-semibold">{fmtNum(ohlc.high)}</span>
            </span>
            <span>
              <span className="text-gray-400">L </span>
              <span className="text-red-500 font-semibold">{fmtNum(ohlc.low)}</span>
            </span>
            <span>
              <span className="text-gray-400">C </span>
              <span className="text-gray-800 font-semibold">{fmtNum(ohlc.close)}</span>
            </span>
            <span style={{ color: chgColor }} className="font-semibold">
              {isUp ? '+' : ''}{fmtNum(ohlc.change)}{' '}
              ({isUp ? '+' : ''}{ohlc.changePct.toFixed(2)}%)
            </span>
          </>
        ) : (
          <span className="text-gray-300">Loading...</span>
        )}
      </div>

      {/* ── Chart canvas: position:absolute fills the flex space so autoSize works ── */}
      <div className="flex-1 relative" style={{ minHeight: 0 }}>
        <div ref={chartContainerRef} style={{ position: 'absolute', inset: 0 }} />
      </div>
    </div>
  );
}
