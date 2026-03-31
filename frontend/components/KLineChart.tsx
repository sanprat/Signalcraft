'use client';

import React, { useEffect, useMemo, useRef } from 'react';
import type { ActionType, Chart, DataLoader, KLineData } from 'klinecharts';
import { dispose, init, registerOverlay } from 'klinecharts';

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
  annotations?: ChartAnnotation[];
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

export interface ChartAnnotation {
  time: string | number;
  value: number;
  text: string;
  color: string;
  backgroundColor: string;
  side?: 'above' | 'below';
}

let tradeSignalOverlayRegistered = false;

function ensureTradeSignalOverlayRegistered() {
  if (tradeSignalOverlayRegistered) {
    return;
  }

  registerOverlay({
    name: 'tradeSignalMarker',
    totalStep: 1,
    lock: true,
    visible: true,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ overlay, coordinates, bounding }) => {
      const point = coordinates[0];
      const data = (overlay.extendData ?? {}) as ChartAnnotation;

      if (!point) {
        return [];
      }

      const side = data.side === 'below' ? 'below' : 'above';
      const direction = side === 'below' ? 1 : -1;
      const lineGap = 10;
      const labelOffset = 28;
      const lineEndY = point.y + lineGap * direction;
      const desiredLabelY = point.y + labelOffset * direction;
      const labelY = Math.max(18, Math.min(bounding.height - 18, desiredLabelY));
      const baseline = side === 'below' ? 'top' : 'bottom';

      return [
        {
          type: 'circle',
          attrs: { x: point.x, y: point.y, r: 4 },
          styles: {
            color: data.backgroundColor,
            borderColor: data.color,
            borderSize: 2,
          },
          ignoreEvent: true,
        },
        {
          type: 'line',
          attrs: {
            coordinates: [
              { x: point.x, y: point.y },
              { x: point.x, y: lineEndY },
            ],
          },
          styles: {
            color: data.color,
            size: 2,
            style: 'solid',
          },
          ignoreEvent: true,
        },
        {
          type: 'text',
          attrs: {
            x: point.x,
            y: labelY,
            text: data.text,
            align: 'center',
            baseline,
          },
          styles: {
            style: 'stroke_fill',
            color: data.color,
            size: 12,
            weight: 700,
            backgroundColor: data.backgroundColor,
            borderColor: data.color,
            borderSize: 1,
            borderRadius: 4,
            paddingLeft: 8,
            paddingRight: 8,
            paddingTop: 4,
            paddingBottom: 4,
          },
          ignoreEvent: true,
        },
      ];
    },
  });

  tradeSignalOverlayRegistered = true;
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

export default function KLineChart({
  data,
  indicators,
  realtimeData,
  isIntraday = false,
  interval,
  symbol,
  annotations,
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

  const normalizedAnnotations = useMemo(() => {
    return (annotations ?? []).map((annotation) => ({
      ...annotation,
      timestamp: normalizeTimestamp(annotation.time, isIntraday),
    }));
  }, [annotations, isIntraday]);

  useEffect(() => {
    ensureTradeSignalOverlayRegistered();
  }, []);

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
    const chart = chartRef.current;
    if (!chart) {
      return;
    }

    chart.removeOverlay();

    normalizedAnnotations.forEach((annotation) => {
      chart.createOverlay({
        name: 'tradeSignalMarker',
        points: [{ timestamp: annotation.timestamp, value: annotation.value }],
        extendData: annotation,
        lock: true,
        zLevel: 80,
      });
    });
  }, [normalizedAnnotations]);

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
