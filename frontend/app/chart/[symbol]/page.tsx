'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { ArrowLeft, Loader2, Zap, Plus, X } from 'lucide-react';
import { config } from '@/lib/config';
import { useQuotes } from '@/hooks/useQuotes';

// Lightweight charts needs to be dynamically imported with SSR disabled
const TradingViewChart = dynamic(
    () => import('@/components/TradingViewChart'),
    { ssr: false }
);

// ─── Indicator Helpers ───────────────────────────────────────────────────────

function calculateSMA(data: any[], period: number) {
    if (data.length < period) return [];
    const result: any[] = [];
    for (let i = period - 1; i < data.length; i++) {
        let sum = 0;
        for (let j = 0; j < period; j++) {
            sum += data[i - j].close;
        }
        result.push({ time: data[i].time, value: sum / period });
    }
    return result;
}

function calculateEMA(data: any[], period: number) {
    if (data.length === 0) return [];
    const k = 2 / (period + 1);
    let ema = data[0].close;
    const result: any[] = [];
    for (let i = 0; i < data.length; i++) {
        ema = data[i].close * k + ema * (1 - k);
        result.push({ time: data[i].time, value: ema });
    }
    return result;
}

// Distinct colors for up to 6 indicators
const INDICATOR_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899'];

type IndicatorEntry = { id: number; type: 'sma' | 'ema'; period: number };

// ─── Component ───────────────────────────────────────────────────────────────

export default function ChartSymbolPage() {
    const params = useParams();
    const router = useRouter();
    const rawSymbol = params?.symbol as string;
    const symbol = rawSymbol ? decodeURIComponent(rawSymbol).toUpperCase() : '';

    const [data, setData] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [isIntraday, setIsIntraday] = useState(false);
    const [interval, setInterval] = useState('1D');

    // Lock parent <main> overflow so the chart page fills exactly 100vh
    // (root layout has overflow:auto on <main> which would allow scrolling past the header)
    useEffect(() => {
        const mainEl = document.querySelector('main') as HTMLElement | null;
        if (mainEl) {
            const prev = mainEl.style.overflow;
            mainEl.style.overflow = 'hidden';
            return () => { mainEl.style.overflow = prev; };
        }
    }, []);

    // Live Data Integration
    const { quotes, connected, subscribe, lastUpdate, isLive } = useQuotes(config.apiBaseUrl);
    const brokerName = isLive ? 'Dhan' : 'Simulated';
    const quoteKey = symbol === 'NIFTY' ? 'NIFTY 50' : symbol;
    const livePrice = quotes[quoteKey]?.ltp;
    const [realtimeCandle, setRealtimeCandle] = useState<any>(null);

    // Price info: use live price if available, otherwise latest historical close
    const displayPrice = livePrice || (data.length > 0 ? data[data.length - 1].close : null);

    // Previous close = second-to-last bar (the day before)
    const previousClose = useMemo(() => {
        if (data.length < 2) return null;
        return data[data.length - 2].close;
    }, [data]);

    const priceChange = displayPrice && previousClose ? displayPrice - previousClose : null;
    const priceChangePct = priceChange && previousClose ? (priceChange / previousClose) * 100 : null;
    const hasLiveFeed = !!livePrice;

    // Multiple Indicator Support
    const [activeIndicators, setActiveIndicators] = useState<IndicatorEntry[]>([]);
    const [nextId, setNextId] = useState(0);

    const addIndicator = (type: 'sma' | 'ema', period: number) => {
        if (activeIndicators.length >= 6) return; // max 6
        setActiveIndicators(prev => [...prev, { id: nextId, type, period }]);
        setNextId(prev => prev + 1);
    };

    const removeIndicator = (id: number) => {
        setActiveIndicators(prev => prev.filter(ind => ind.id !== id));
    };

    useEffect(() => {
        if (!symbol) return;

        const fetchHistoricalData = async () => {
            try {
                setLoading(true);
                const res = await fetch(`${config.apiBaseUrl}/api/quotes/historical/${symbol}?interval=${interval}`);
                const json = await res.json();

                if (json.error) {
                    setError(json.error);
                } else if (json.data && json.data.length > 0) {
                    setData(json.data);
                    setIsIntraday(!!json.is_intraday);
                } else {
                    setError('No historical data found for this symbol.');
                }
            } catch (err) {
                setError('Failed to connect to the pricing server.');
            } finally {
                setLoading(false);
            }
        };

        fetchHistoricalData();
    }, [symbol, interval]);

    // Subscribe to symbol on connect
    useEffect(() => {
        if (connected && symbol) {
            subscribe(symbol);
        }
    }, [connected, symbol, subscribe]);

    // Handle Live Ticking
    useEffect(() => {
        if (!livePrice || data.length === 0) return;

        const lastBar = data[data.length - 1];
        const today = new Date().toISOString().split('T')[0];

        if (isIntraday) {
            const now = Math.floor(Date.now() / 1000);
            setRealtimeCandle({
                time: now,
                open: livePrice,
                high: livePrice,
                low: livePrice,
                close: livePrice
            });
        } else if (lastBar.time === today) {
            setRealtimeCandle({
                time: lastBar.time,
                open: lastBar.open,
                high: Math.max(lastBar.high, livePrice),
                low: Math.min(lastBar.low, livePrice),
                close: livePrice
            });
        } else {
            setRealtimeCandle({
                time: today,
                open: livePrice,
                high: livePrice,
                low: livePrice,
                close: livePrice
            });
        }
    }, [livePrice, data, isIntraday]);

    // Compute all active indicators
    const indicators = useMemo(() => {
        if (data.length === 0 || activeIndicators.length === 0) return [];

        return activeIndicators.map((ind, index) => {
            const calc = ind.type === 'sma' ? calculateSMA : calculateEMA;
            const lineData = calc(data, ind.period);
            const label = ind.type.toUpperCase();
            return {
                name: `${label} ${ind.period}`,
                data: lineData,
                color: INDICATOR_COLORS[index % INDICATOR_COLORS.length],
                lineWidth: 2,
            };
        });
    }, [activeIndicators, data]);

    const isIndex = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'GIFTNIFTY'].includes(symbol);

    return (
        <div style={{ height: '100dvh', overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: '16px 24px 12px' }}>
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => router.push('/chart')}
                        className="p-2 hover:bg-gray-100 rounded-full transition"
                    >
                        <ArrowLeft className="w-5 h-5 text-gray-600" />
                    </button>
                    <div>
                        <div className="flex items-center gap-2">
                            <h1 className="text-2xl font-bold text-gray-900">{symbol}</h1>
                            {connected && <Zap className="w-4 h-4 text-amber-500 fill-amber-500" />}
                        </div>
                        <p className="text-sm text-gray-500">
                            {isIntraday ? `${interval} Intraday` : '1D Daily'} · {connected ? `${brokerName} Updates: ${lastUpdate}` : 'Connecting...'}
                        </p>
                    </div>
                </div>
                <Link
                    href={`/dashboard?segment=${isIndex ? 'Options' : 'Stocks'}`}
                    className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-semibold transition"
                >
                    🏠 Back to Dashboard
                </Link>
            </div>

            {/* ─── Live Price Info Panel ──────────────────────────────────── */}
            {displayPrice && (
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '16px', marginBottom: '12px', paddingLeft: '4px' }}>
                    <span style={{ fontSize: '1.875rem', fontWeight: 700, color: '#111827', fontVariantNumeric: 'tabular-nums' }}>
                        {displayPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                    <span style={{ fontSize: '0.875rem', fontWeight: 500, color: '#9ca3af' }}>INR</span>
                    {priceChange !== null && priceChangePct !== null && (
                        <span style={{
                            fontSize: '0.875rem',
                            fontWeight: 600,
                            fontVariantNumeric: 'tabular-nums',
                            color: priceChange >= 0 ? '#059669' : '#ef4444'
                        }}>
                            {priceChange >= 0 ? '+' : ''}
                            {priceChange.toFixed(2)}
                            {' ('}
                            {priceChange >= 0 ? '+' : ''}
                            {priceChangePct.toFixed(2)}%{')'}
                        </span>
                    )}
                    {hasLiveFeed && connected ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', fontWeight: 500, color: '#059669' }}>
                            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981', animation: 'pulse 2s infinite' }} />
                            Live
                        </span>
                    ) : (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', fontWeight: 500, color: '#9ca3af' }}>
                            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#d1d5db' }} />
                            Last Close
                        </span>
                    )}
                </div>
            )}

            {/* Timeframe Selector & Indicator Controls */}
            <div className="flex flex-wrap items-center gap-4 mb-4 bg-gray-50 rounded-lg px-4 py-2.5 border border-gray-200">
                <div className="flex items-center gap-2 pr-4 border-r border-gray-200">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Timeframe</span>
                    <div className="flex bg-white rounded border border-gray-200 p-0.5">
                        {['1s', '5s', '1min', '5min', '15min', '1D'].map((tf) => (
                            <button
                                key={tf}
                                onClick={() => setInterval(tf)}
                                className={`px-2 py-0.5 text-xs font-medium rounded transition ${interval === tf
                                        ? 'bg-blue-600 text-white'
                                        : 'text-gray-500 hover:bg-gray-100'
                                    }`}
                            >
                                {tf}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 flex-1">

                    {/* Active indicator pills */}
                    {activeIndicators.map((ind, index) => (
                        <span
                            key={ind.id}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold text-white"
                            style={{ backgroundColor: INDICATOR_COLORS[index % INDICATOR_COLORS.length] }}
                        >
                            {ind.type.toUpperCase()} {ind.period}
                            <button
                                onClick={() => removeIndicator(ind.id)}
                                className="ml-0.5 hover:opacity-75 transition"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        </span>
                    ))}

                    {/* Quick-add buttons */}
                    <div className="flex items-center gap-1 ml-auto">
                        <span className="text-xs text-gray-400 mr-1">Add:</span>
                        {[
                            { type: 'sma' as const, period: 9 },
                            { type: 'sma' as const, period: 20 },
                            { type: 'sma' as const, period: 50 },
                            { type: 'ema' as const, period: 9 },
                            { type: 'ema' as const, period: 21 },
                            { type: 'ema' as const, period: 50 },
                        ].map(preset => {
                            const isActive = activeIndicators.some(
                                a => a.type === preset.type && a.period === preset.period
                            );
                            return (
                                <button
                                    key={`${preset.type}-${preset.period}`}
                                    onClick={() => {
                                        if (isActive) {
                                            const entry = activeIndicators.find(
                                                a => a.type === preset.type && a.period === preset.period
                                            );
                                            if (entry) removeIndicator(entry.id);
                                        } else {
                                            addIndicator(preset.type, preset.period);
                                        }
                                    }}
                                    className={`px-2 py-1 rounded text-xs font-medium transition border ${isActive
                                        ? 'bg-blue-600 text-white border-blue-600'
                                        : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-100'
                                        }`}
                                >
                                    {preset.type.toUpperCase()} {preset.period}
                                </button>
                            );
                        })}
                    </div>
                </div>
            </div>

            <div className="flex-1 flex flex-col" style={{ minHeight: 0 }}>
                {loading ? (
                    <div className="flex flex-col items-center text-gray-400 gap-3 m-auto">
                        <Loader2 className="w-8 h-8 animate-spin" />
                        <p>Loading chart data...</p>
                    </div>
                ) : error ? (
                    <div className="text-red-500 font-medium bg-red-50 px-6 py-4 rounded-lg m-auto">
                        {error}
                    </div>
                ) : data.length > 0 ? (
                    <TradingViewChart
                        data={data.map(d => ({
                            time: d.time,
                            open: d.open,
                            high: d.high,
                            low: d.low,
                            close: d.close
                        }))}
                        volumeData={data.map(d => ({
                            time: d.time,
                            value: d.value,
                            color: d.open > d.close ? 'rgba(242, 54, 69, 0.5)' : 'rgba(8, 153, 129, 0.5)'
                        }))}
                        indicators={indicators}
                        realtimeData={realtimeCandle}
                        isIntraday={isIntraday}
                        symbol={symbol}
                    />
                ) : (
                    <p className="text-gray-400 m-auto">No chart data available.</p>
                )}
            </div>
        </div>
    );
}
