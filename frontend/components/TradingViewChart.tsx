'use client';

import React, { useEffect, useMemo, useRef } from 'react';
import type { ActionType, Chart, DataLoader, KLineData } from 'klinecharts';
import { dispose, init } from 'klinecharts';

export interface IndicatorPoint {
  time: string | number;
  value: number;
}

export interface IndicatorConfig {
  name: string;
  data: IndicatorPoint[];
  color: string;
  lineWidth?: number;
}

export interface ChartProps {
  data: Array<{
    time: string | number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }>;
  volumeData?: { time: string | number; value: number; color?: string }[];
  indicators?: IndicatorConfig[];
  realtimeData?: {
    time: string | number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  } | null;
  isIntraday?: boolean;
  interval?: string;
  symbol?: string;
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

function normalizeTimestamp(value: string | number, isIntraday: boolean): number {
  if (typeof value === 'number') {
    return value > 1_000_000_000_000 ? value : value * 1000;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return new Date(`${value}T09:15:00+05:30`).getTime();
  }

  const parsed = new Date(value).getTime();
  if (!Number.isNaN(parsed)) {
    return parsed;
  }

  return isIntraday ? Date.now() : new Date(`${value}T09:15:00+05:30`).getTime();
}

function formatHoverTime(timestampMs: number, isIntraday: boolean): string {
  const date = new Date(timestampMs);
  const options = isIntraday
    ? { dateStyle: 'short', timeStyle: 'short' }
    : { dateStyle: 'short' };
  return new Intl.DateTimeFormat('en-IN', options as Intl.DateTimeFormatOptions).format(date);
}

function getPeriod(interval?: string) {
  switch (interval) {
    case '1s':
      return { type: 'second' as const, span: 1 };
    case '5s':
      return { type: 'second' as const, span: 5 };
    case '1min':
      return { type: 'minute' as const, span: 1 };
    case '5min':
      return { type: 'minute' as const, span: 5 };
    case '15min':
      return { type: 'minute' as const, span: 15 };
    case '1D':
    default:
      return { type: 'day' as const, span: 1 };
  }
}

export default function TradingViewChart({
  data,
  indicators,
  realtimeData,
  isIntraday = false,
  interval,
  symbol,
  onCrosshairMove,
}: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<Chart | null>(null);
  const pushBarRef = useRef<((data: KLineData) => void) | null>(null);
  const crosshairHandlerRef = useRef<((data?: unknown) => void) | null>(null);

  const normalizedData = useMemo<KLineData[]>(() => {
    return data.map((bar) => ({
      timestamp: normalizeTimestamp(bar.time, isIntraday),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume ?? 0,
    }));
  }, [data, isIntraday]);

  const indicatorMaps = useMemo(() => {
    return (indicators ?? []).map((indicator) => ({
      ...indicator,
      valueMap: new Map(
        indicator.data.map((point) => [
          normalizeTimestamp(point.time, isIntraday),
          point.value,
        ]),
      ),
    }));
  }, [indicators, isIntraday]);

  useEffect(() => {
    if (!containerRef.current || !normalizedData.length) {
      return;
    }

    const chart = init(containerRef.current, {
      timezone: 'Asia/Kolkata',
      styles: {
        grid: {
          horizontal: { color: '#F1F5F9', show: true },
          vertical: { color: '#F8FAFC', show: true },
        },
        candle: {
          bar: {
            upColor: '#089981',
            downColor: '#f23645',
            noChangeColor: '#94A3B8',
            upBorderColor: '#089981',
            downBorderColor: '#f23645',
            noChangeBorderColor: '#94A3B8',
            upWickColor: '#089981',
            downWickColor: '#f23645',
            noChangeWickColor: '#94A3B8',
          },
        },
      },
    });

    if (!chart) {
      return;
    }

    chartRef.current = chart;
    chart.setTimezone('Asia/Kolkata');
    chart.setSymbol({
      ticker: symbol || 'CHART',
      pricePrecision: 2,
      volumePrecision: 0,
    });
    chart.setPeriod(getPeriod(interval));

    const dataLoader: DataLoader = {
      getBars: ({ callback }) => {
        callback(normalizedData, false);
      },
      subscribeBar: ({ callback }) => {
        pushBarRef.current = callback;
      },
      unsubscribeBar: () => {
        pushBarRef.current = null;
      },
    };

    chart.setDataLoader(dataLoader);

    if (normalizedData.some((bar) => (bar.volume ?? 0) > 0)) {
      chart.createIndicator('VOL', false, { id: 'volume-pane', height: 96, minHeight: 72 });
    }

    indicatorMaps.forEach((indicator, index) => {
      chart.createIndicator(
        {
          name: `overlay_${indicator.name}_${index}`,
          shortName: indicator.name,
          series: 'price',
          precision: 2,
          calcParams: [],
          shouldOhlc: false,
          shouldFormatBigNumber: false,
          visible: true,
          zLevel: 20 + index,
          figures: [
            {
              key: 'value',
              title: indicator.name,
              type: 'line',
              styles: () => ({
                color: indicator.color,
                size: indicator.lineWidth ?? 2,
              }),
            },
          ],
          calc: (dataList: KLineData[]) =>
            dataList.map((bar) => ({
              value: indicator.valueMap.get(bar.timestamp) ?? Number.NaN,
            })),
        },
        false,
      );
    });

    if (onCrosshairMove) {
      const handler = (raw?: unknown) => {
        const crosshair = raw as {
          timestamp?: number;
          dataIndex?: number;
          kLineData?: KLineData;
        };

        if (!crosshair?.timestamp || !crosshair.kLineData) {
          onCrosshairMove(null);
          return;
        }

        const currentIndex =
          typeof crosshair.dataIndex === 'number'
            ? crosshair.dataIndex
            : normalizedData.findIndex((bar) => bar.timestamp === crosshair.timestamp);

        const currentBar = crosshair.kLineData;
        const prevBar = currentIndex > 0 ? normalizedData[currentIndex - 1] : null;
        const prevClose = prevBar?.close ?? currentBar.open;
        const change = currentBar.close - prevClose;

        onCrosshairMove({
          time: formatHoverTime(crosshair.timestamp, isIntraday),
          open: currentBar.open,
          high: currentBar.high,
          low: currentBar.low,
          close: currentBar.close,
          change,
          changePct: prevClose ? (change / prevClose) * 100 : 0,
        });
      };

      crosshairHandlerRef.current = handler;
      chart.subscribeAction('onCrosshairChange' as ActionType, handler);
    }

    return () => {
      if (crosshairHandlerRef.current) {
        chart.unsubscribeAction('onCrosshairChange' as ActionType, crosshairHandlerRef.current);
      }
      pushBarRef.current = null;
      crosshairHandlerRef.current = null;
      dispose(containerRef.current!);
      chartRef.current = null;
    };
  }, [indicatorMaps, interval, isIntraday, normalizedData, onCrosshairMove, symbol]);

  useEffect(() => {
    if (!realtimeData || !pushBarRef.current) {
      return;
    }

    pushBarRef.current({
      timestamp: normalizeTimestamp(realtimeData.time, isIntraday),
      open: realtimeData.open,
      high: realtimeData.high,
      low: realtimeData.low,
      close: realtimeData.close,
      volume: realtimeData.volume ?? 0,
    });
  }, [isIntraday, realtimeData]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', minHeight: 0 }}>
      <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
    </div>
  );
}
