'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { ArrowLeft, Zap, X } from 'lucide-react';
import { config } from '@/lib/config';
import { useQuotes } from '@/hooks/useQuotes';
import type { HoveredBar } from '@/components/TradingViewChart';

const TradingViewChart = dynamic(() => import('@/components/TradingViewChart'), { ssr: false });

// ─── Indicator helpers ────────────────────────────────────────────────────────

function calculateSMA(data: any[], period: number) {
  if (data.length < period) return [];
  const result: any[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].close;
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}

function calculateEMA(data: any[], period: number) {
  if (!data.length) return [];
  const k = 2 / (period + 1);
  let ema = data[0].close;
  return data.map(d => {
    ema = d.close * k + ema * (1 - k);
    return { time: d.time, value: ema };
  });
}

function fmtNum(n: number) {
  return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const INDICATOR_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899'];
const TIMEFRAMES = ['1s', '5s', '1min', '5min', '15min', '1D'] as const;
const MA_PRESETS = [
  { type: 'sma' as const, period: 9 },
  { type: 'sma' as const, period: 20 },
  { type: 'sma' as const, period: 50 },
  { type: 'ema' as const, period: 9 },
  { type: 'ema' as const, period: 21 },
  { type: 'ema' as const, period: 50 },
];

type IndicatorEntry = { id: number; type: 'sma' | 'ema'; period: number };

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChartSymbolPage() {
  const params = useParams();
  const router = useRouter();
  const symbol = params?.symbol
    ? decodeURIComponent(params.symbol as string).toUpperCase()
    : '';

  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isIntraday, setIsIntraday] = useState(false);
  const [interval, setInterval] = useState('1D');

  // Live data
  const { quotes, connected, subscribe, lastUpdate, isLive } = useQuotes(config.apiBaseUrl);
  const brokerName = isLive ? 'Dhan' : 'Simulated';
  const quoteKey = symbol === 'NIFTY' ? 'NIFTY 50' : symbol;
  const livePrice = quotes[quoteKey]?.ltp;
  const [realtimeCandle, setRealtimeCandle] = useState<any>(null);

  // OHLC bar — starts from last historical bar, updated by crosshair
  const lastBar = data.length ? data[data.length - 1] : null;
  const prevBar  = data.length > 1 ? data[data.length - 2] : null;
  const [hoveredBar, setHoveredBar] = useState<HoveredBar | null>(null);

  // livePrice=0 means backend subscribed but no tick received yet — treat as no data
  const livePriceValid = typeof livePrice === 'number' && livePrice > 0;

  // Displayed price = live tick > crosshair close > last bar close
  const displayClose  = hoveredBar?.close  ?? (livePriceValid ? livePrice! : (lastBar?.close ?? 0));
  const displayOpen   = hoveredBar?.open   ?? lastBar?.open   ?? 0;
  const displayHigh   = hoveredBar?.high   ?? lastBar?.high   ?? 0;
  const displayLow    = hoveredBar?.low    ?? lastBar?.low    ?? 0;
  const displayChange = hoveredBar
    ? hoveredBar.change
    : livePriceValid && prevBar
      ? livePrice! - prevBar.close
      : lastBar && prevBar
        ? lastBar.close - prevBar.close
        : 0;
  const displayChangePct = hoveredBar
    ? hoveredBar.changePct
    : prevBar && prevBar.close
      ? (displayChange / prevBar.close) * 100
      : 0;

  // True only when we have a real non-zero live tick for this symbol
  const isShowingLive = livePriceValid && !hoveredBar;

  const isUp = displayChange >= 0;
  const chgColor = isUp ? '#16a34a' : '#dc2626';

  // Indicators
  const [activeIndicators, setActiveIndicators] = useState<IndicatorEntry[]>([]);
  const [nextId, setNextId] = useState(0);

  const addIndicator = (type: 'sma' | 'ema', period: number) => {
    if (activeIndicators.length >= 6) return;
    setActiveIndicators(prev => [...prev, { id: nextId, type, period }]);
    setNextId(n => n + 1);
  };
  const removeIndicator = (id: number) =>
    setActiveIndicators(prev => prev.filter(i => i.id !== id));

  const indicators = useMemo(() => {
    if (!data.length || !activeIndicators.length) return [];
    return activeIndicators.map((ind, i) => ({
      name: `${ind.type.toUpperCase()} ${ind.period}`,
      data: (ind.type === 'sma' ? calculateSMA : calculateEMA)(data, ind.period),
      color: INDICATOR_COLORS[i % INDICATOR_COLORS.length],
      lineWidth: 2,
    }));
  }, [activeIndicators, data]);

  // Fetch historical data
  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError('');
    fetch(`${config.apiBaseUrl}/api/quotes/historical/${symbol}?interval=${interval}`)
      .then(r => r.json())
      .then(json => {
        if (json.error) { setError(json.error); return; }
        if (json.data?.length) {
          setData(json.data);
          setIsIntraday(!!json.is_intraday);
        } else {
          setError('No data found for this symbol.');
        }
      })
      .catch(() => setError('Failed to connect to the pricing server.'))
      .finally(() => setLoading(false));
  }, [symbol, interval]);

  useEffect(() => {
    if (connected && symbol) subscribe(symbol);
  }, [connected, symbol, subscribe]);

  useEffect(() => {
    // Clear stale candle when livePrice is 0/undefined (e.g. between reconnects)
    if (!livePriceValid || !data.length) {
      setRealtimeCandle(null);
      return;
    }
    const lastBar = data[data.length - 1];
    const prevClose = data.length > 1 ? data[data.length - 2].close : lastBar.close;
    const today = new Date().toISOString().split('T')[0];

    if (isIntraday) {
      const now = Math.floor(Date.now() / 1000);
      setRealtimeCandle({ time: now, open: livePrice!, high: livePrice!, low: livePrice!, close: livePrice! });
    } else if (lastBar.time === today) {
      // Update today's existing historical bar
      setRealtimeCandle({
        time: lastBar.time,
        open: lastBar.open,
        high: Math.max(lastBar.high, livePrice!),
        low:  Math.min(lastBar.low,  livePrice!),
        close: livePrice!,
      });
    } else {
      // New trading day: use prev close as open so we get a proper candle
      // (not a flat spike that looks like a 34% crash)
      const dayOpen = prevClose ?? livePrice!;
      setRealtimeCandle({
        time:  today,
        open:  dayOpen,
        high:  Math.max(dayOpen, livePrice!),
        low:   Math.min(dayOpen, livePrice!),
        close: livePrice!,
      });
    }
  }, [livePriceValid, livePrice, data, isIntraday]);


  const handleCrosshairMove = useCallback((bar: HoveredBar | null) => {
    setHoveredBar(bar);
  }, []);

  const isIndex = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'GIFTNIFTY'].includes(symbol);
  const volumeData = data.map(d => ({
    time: d.time,
    value: d.volume ?? d.value ?? 0,
  }));

  return (
    <div style={{
      position: 'fixed', inset: 0, overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
      background: '#F8FAFC', zIndex: 50,
    }}>

      {/* ══════════════════════════════════════════════════
          HEADER
      ══════════════════════════════════════════════════ */}
      <div style={{
        flexShrink: 0,
        background: '#ffffff',
        borderBottom: '1px solid #E5E7EB',
      }}>

        {/* Row 1 — Nav + Symbol + Live badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '10px 16px 0',
        }}>
          <button
            onClick={() => router.push('/chart')}
            style={{
              padding: 6, borderRadius: 8, border: 'none', background: 'transparent',
              cursor: 'pointer', color: '#6B7280', display: 'flex', alignItems: 'center',
            }}
          >
            <ArrowLeft size={18} />
          </button>

          <span style={{ fontSize: 20, fontWeight: 700, color: '#111827', letterSpacing: '-0.5px' }}>
            {symbol}
          </span>

          {connected && (
            <span style={{
              display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 11, fontWeight: 600, color: '#16a34a',
              background: '#f0fdf4', border: '1px solid #bbf7d0',
              padding: '2px 8px', borderRadius: 20,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#16a34a', animation: 'pulse 2s infinite',
              }} />
              {brokerName} · {lastUpdate}
            </span>
          )}

          {/* Show when we DON'T have a live price — data is last historical close */}
          {connected && !isShowingLive && (
            <span style={{
              display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 11, fontWeight: 600, color: '#92400e',
              background: '#fffbeb', border: '1px solid #fde68a',
              padding: '2px 8px', borderRadius: 20,
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b' }} />
              Prev Close
            </span>
          )}

          <div style={{ marginLeft: 'auto' }}>
            <Link
              href={`/dashboard?segment=${isIndex ? 'Options' : 'Stocks'}`}
              style={{
                fontSize: 13, fontWeight: 500, color: '#6B7280',
                textDecoration: 'none', padding: '6px 12px',
                background: '#F3F4F6', borderRadius: 8,
              }}
            >
              ← Dashboard
            </Link>
          </div>
        </div>

        {/* Row 2 — Price + Change + OHLC */}
        <div style={{
          display: 'flex', alignItems: 'baseline', flexWrap: 'wrap',
          gap: 12, padding: '6px 16px 0',
        }}>
          {/* Big price */}
          <span style={{
            fontSize: 30, fontWeight: 700, color: '#111827',
            fontVariantNumeric: 'tabular-nums', letterSpacing: '-1px',
          }}>
            {fmtNum(displayClose)}
          </span>
          <span style={{ fontSize: 13, color: '#9CA3AF', fontWeight: 500 }}>INR</span>

          {/* Change */}
          <span style={{ fontSize: 15, fontWeight: 600, color: chgColor, fontVariantNumeric: 'tabular-nums' }}>
            {isUp ? '+' : ''}{fmtNum(displayChange)}&nbsp;
            ({isUp ? '+' : ''}{displayChangePct.toFixed(2)}%)
          </span>

          {/* Divider */}
          <span style={{ width: 1, height: 18, background: '#E5E7EB', alignSelf: 'center' }} />

          {/* OHLC */}
          {[
            { label: 'O', value: displayOpen,  color: '#374151' },
            { label: 'H', value: displayHigh,  color: '#059669' },
            { label: 'L', value: displayLow,   color: '#dc2626' },
            { label: 'C', value: displayClose, color: '#111827' },
          ].map(({ label, value, color }) => (
            <span key={label} style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
              <span style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 600, letterSpacing: '0.05em' }}>
                {label}
              </span>
              <span style={{ fontSize: 13, fontWeight: 600, color, fontVariantNumeric: 'tabular-nums' }}>
                {fmtNum(value)}
              </span>
            </span>
          ))}

          {/* Active indicator pills */}
          {activeIndicators.map((ind, i) => (
            <span
              key={ind.id}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                padding: '2px 8px', borderRadius: 20,
                fontSize: 11, fontWeight: 600, color: '#fff',
                background: INDICATOR_COLORS[i % INDICATOR_COLORS.length],
              }}
            >
              {ind.type.toUpperCase()} {ind.period}
              <button
                onClick={() => removeIndicator(ind.id)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#fff', padding: 0, display: 'flex' }}
              >
                <X size={11} />
              </button>
            </span>
          ))}
        </div>

        {/* Row 3 — Timeframe + MA buttons */}
        <div style={{
          display: 'flex', alignItems: 'center', flexWrap: 'wrap',
          gap: 8, padding: '8px 16px 10px',
        }}>
          {/* Timeframe label */}
          <span style={{ fontSize: 11, fontWeight: 600, color: '#9CA3AF', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Timeframe
          </span>

          {/* TF buttons */}
          <div style={{ display: 'flex', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 8, padding: 2 }}>
            {TIMEFRAMES.map(tf => (
              <button
                key={tf}
                onClick={() => setInterval(tf)}
                style={{
                  padding: '3px 10px', border: 'none', cursor: 'pointer',
                  borderRadius: 6, fontSize: 12, fontWeight: 600,
                  transition: 'all 0.15s',
                  background: interval === tf ? '#1D4ED8' : 'transparent',
                  color: interval === tf ? '#fff' : '#6B7280',
                }}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Divider */}
          <span style={{ width: 1, height: 18, background: '#E5E7EB' }} />

          {/* MA label */}
          <span style={{ fontSize: 11, fontWeight: 600, color: '#9CA3AF', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Add
          </span>

          {/* MA preset buttons */}
          {MA_PRESETS.map(preset => {
            const activeEntry = activeIndicators.find(
              a => a.type === preset.type && a.period === preset.period
            );
            const isActive = !!activeEntry;
            const colorIdx = isActive
              ? activeIndicators.findIndex(a => a.id === activeEntry!.id)
              : -1;
            return (
              <button
                key={`${preset.type}-${preset.period}`}
                onClick={() => {
                  if (isActive) removeIndicator(activeEntry!.id);
                  else addIndicator(preset.type, preset.period);
                }}
                style={{
                  padding: '3px 10px', cursor: 'pointer',
                  borderRadius: 6, fontSize: 12, fontWeight: 600,
                  transition: 'all 0.15s',
                  border: isActive
                    ? `1.5px solid ${INDICATOR_COLORS[colorIdx % INDICATOR_COLORS.length]}`
                    : '1.5px solid #E5E7EB',
                  background: isActive
                    ? `${INDICATOR_COLORS[colorIdx % INDICATOR_COLORS.length]}18`
                    : '#fff',
                  color: isActive
                    ? INDICATOR_COLORS[colorIdx % INDICATOR_COLORS.length]
                    : '#6B7280',
                }}
              >
                {preset.type.toUpperCase()} {preset.period}
              </button>
            );
          })}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════
          CHART AREA
      ══════════════════════════════════════════════════ */}
      <div style={{ flex: 1, minHeight: 0, padding: '12px 16px 12px' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#9CA3AF', fontSize: 14 }}>
            Loading chart data…
          </div>
        ) : error ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', padding: '12px 20px', borderRadius: 8, fontSize: 14 }}>
              {error}
            </div>
          </div>
        ) : data.length ? (
          <div style={{ width: '100%', height: '100%', borderRadius: 12, overflow: 'hidden', border: '1px solid #E5E7EB', background: '#fff' }}>
            <TradingViewChart
              data={data.map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close }))}
              volumeData={volumeData}
              indicators={indicators}
              realtimeData={realtimeCandle}
              isIntraday={isIntraday}
              symbol={symbol}
              onCrosshairMove={handleCrosshairMove}
            />
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#9CA3AF' }}>
            No chart data available.
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
