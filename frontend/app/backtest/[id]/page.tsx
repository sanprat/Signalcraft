'use client'

import { useEffect, useMemo, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { config, getAuthHeaders } from '@/lib/config'
import KLineChart, { ChartAnnotation, normalizeChartInterval } from '@/components/KLineChart'

const API = config.apiBaseUrl

const T = {
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF', blueMid: '#BFDBFE',
    green: '#059669', greenLight: '#ECFDF5', greenMid: '#A7F3D0',
    red: '#DC2626', redLight: '#FEF2F2', redMid: '#FECACA',
    amber: '#D97706', amberLight: '#FFFBEB',
    text: '#0F172A', textMid: '#475569', textMuted: '#94A3B8',
    border: '#E2E8F0', borderStrong: '#CBD5E1', surface: '#FFFFFF', bg: '#F8FAFC',
}

type Summary = {
    backtest_id: string; strategy_id?: string; total_trades: number
    winning_trades: number; losing_trades: number; win_rate: number
    total_pnl: number; max_drawdown: number; avg_trade_pnl: number
    best_trade: number; worst_trade: number; candle_count: number; date_range: string
    symbol?: string; symbols?: string[]
    timeframe?: string; strategy_name?: string
}

type Trade = {
    trade_no: number; entry_time: string; entry_price: number
    exit_time: string; exit_price: number; pnl: number; pnl_pct: number; exit_reason: string
    symbol?: string
}

type StrategyMeta = {
    name?: string
    timeframe?: string
    symbol?: string
    symbols?: string[]
}

function Card({ children, style = {} }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return <div style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`, boxShadow: '0 1px 3px rgba(0,0,0,0.04)', padding: 20, ...style }}>{children}</div>
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
    return (
        <Card style={{ padding: '16px 20px', textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: T.textMuted, fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 8 }}>{label}</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: color ?? T.navy, fontFamily: "'DM Mono', monospace", letterSpacing: '-0.5px' }}>{value}</div>
        </Card>
    )
}

function fmtMoney(value: number) {
    return value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPercent(value: number) {
    return value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatTimeframe(timeframe?: string) {
    if (!timeframe) return 'Unknown TF'
    // Let the shared normalizer handle canonical short form
    return normalizeChartInterval(timeframe)
}

function isIntraday(interval: string): boolean {
    return !/^1[dw]$/i.test(interval)
}

function getChartSymbol(summary: Summary | null, strategy: StrategyMeta | null, trades: Trade[]) {
    const symbols = strategy?.symbols?.length
        ? strategy.symbols
        : summary?.symbols?.length
            ? summary.symbols
            : [
                strategy?.symbol,
                summary?.symbol,
                trades.find((trade) => trade.symbol)?.symbol,
            ].filter(Boolean) as string[]
    return symbols.length ? symbols.join(', ') : 'Backtest'
}

type ColumnarCandles = {
    time: string[]
    open: number[]
    high: number[]
    low: number[]
    close: number[]
    volume?: number[]
}

type ChartPayload = {
    candles: ColumnarCandles
    annotations: ChartAnnotation[]
    symbol: string
    timeframe: string
    display_from: string
    display_to: string
    full_from: string
    full_to: string
    is_partial: boolean
    has_more_left: boolean
    has_more_right: boolean
}

function normalizeColumnarCandles(columnar: ColumnarCandles): Array<{
    time: string
    open: number
    high: number
    low: number
    close: number
    volume: number
}> {
    return columnar.time.map((t, i) => ({
        time: t,
        open: columnar.open[i],
        high: columnar.high[i],
        low: columnar.low[i],
        close: columnar.close[i],
        volume: columnar.volume?.[i] || 0,
    }))
}

function isValidChartPayload(data: unknown): data is ChartPayload {
    if (!data || typeof data !== 'object') return false
    const obj = data as Record<string, unknown>
    return (
        Array.isArray((obj as any).candles?.time) &&
        Array.isArray((obj as any).candles?.open) &&
        Array.isArray((obj as any).annotations) &&
        typeof (obj as any).is_partial === 'boolean'
    )
}

function BacktestChart({
    backtestId,
    chartTitle,
    chartSymbol,
    interval,
}: {
    backtestId: string
    chartTitle: string
    chartSymbol: string
    interval: string
}) {
    const CACHE_KEY = `chart_${backtestId}`

    const [candles, setCandles] = useState<Array<{
        time: string
        open: number
        high: number
        low: number
        close: number
        volume: number
    }>>([])
    const [annotations, setAnnotations] = useState<ChartAnnotation[]>([])
    const [chartError, setChartError] = useState<string | null>(null)
    const [loadingFull, setLoadingFull] = useState(false)
    const [showFullButton, setShowFullButton] = useState(false)

    const loadChart = async (full = false) => {
        // Check sessionStorage cache first (only for smart-range, not full)
        if (!full) {
            try {
                const cached = sessionStorage.getItem(CACHE_KEY)
                if (cached) {
                    const parsed = JSON.parse(cached)
                    if (isValidChartPayload(parsed)) {
                        setCandles(normalizeColumnarCandles(parsed.candles))
                        setAnnotations(parsed.annotations)
                        if (parsed.is_partial && (parsed.has_more_left || parsed.has_more_right)) {
                            setShowFullButton(true)
                        }
                        setChartError(null)
                        return
                    }
                }
            } catch {
                // Malformed cache, fall through to fetch
            }
        }

        try {
            const endpoint = full
                ? `${API}/api/backtest/${backtestId}/chart?full=1`
                : `${API}/api/backtest/${backtestId}/chart`

            const response = await fetch(endpoint)
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Chart data is not available for this backtest.')
                }
                throw new Error('Failed to load chart data.')
            }

            const chartData: ChartPayload = await response.json()
            if (!isValidChartPayload(chartData)) {
                throw new Error('Chart data is malformed.')
            }

            // Cache in sessionStorage (only for smart-range)
            if (!full) {
                try {
                    sessionStorage.setItem(CACHE_KEY, JSON.stringify(chartData))
                } catch { /* quota exceeded — harmless */ }
            }

            const normalized = normalizeColumnarCandles(chartData.candles)
            setCandles(normalized)
            setAnnotations(chartData.annotations)
            setChartError(normalized.length === 0 ? 'Chart data is empty for this backtest.' : null)

            if (chartData.is_partial && (chartData.has_more_left || chartData.has_more_right)) {
                setShowFullButton(true)
            } else {
                setShowFullButton(false)
            }
        } catch (error: any) {
            setCandles([])
            setAnnotations([])
            setChartError(error?.message || 'Failed to load chart data.')
        } finally {
            if (full) {
                setLoadingFull(false)
            }
        }
    }

    useEffect(() => {
        if (backtestId) {
            loadChart()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [backtestId])

    return (
        <Card>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: T.navy }}>{chartTitle}</span>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: T.green }}>▲ Entry</span>
                    <span style={{ fontSize: 11, color: T.red }}>▼ Exit</span>
                    {showFullButton && !loadingFull && (
                        <button
                            onClick={() => { setLoadingFull(true); loadChart(true) }}
                            style={{
                                marginLeft: 8,
                                padding: '2px 10px',
                                fontSize: 11,
                                fontWeight: 600,
                                border: `1px solid ${T.border}`,
                                borderRadius: 6,
                                background: T.surface,
                                color: T.textMid,
                                cursor: 'pointer',
                            }}
                        >
                            Load Full Range
                        </button>
                    )}
                    {loadingFull && (
                        <span style={{ marginLeft: 8, fontSize: 11, color: T.textMuted }}>Loading full range...</span>
                    )}
                </div>
            </div>
            <div style={{ height: 400, borderRadius: 8, overflow: 'hidden', position: 'relative', background: '#fff', border: `1px solid ${T.border}` }}>
                {candles.length > 0 ? (
                    <KLineChart
                        data={candles}
                        isIntraday={isIntraday(interval)}
                        interval={interval}
                        symbol={chartSymbol}
                        annotations={annotations}
                    />
                ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: T.textMuted, fontSize: 13 }}>
                        {chartError || 'Loading chart data...'}
                    </div>
                )}
            </div>
            {chartError && candles.length === 0 && (
                <div style={{ marginTop: 12, fontSize: 12, color: T.textMuted }}>
                    {chartError}
                </div>
            )}
        </Card>
    )
}

export default function BacktestResultsPage() {
    const { id } = useParams() as { id: string }
    const router = useRouter()
    const [summary, setSummary] = useState<Summary | null>(null)
    const [trades, setTrades] = useState<Trade[]>([])
    const [strategy, setStrategy] = useState<StrategyMeta | null>(null)

    useEffect(() => {
        if (!id) return

        fetch(`${API}/api/backtest/${id}/summary`)
            .then(r => r.json())
            .then((data) => {
                setSummary(data)
                if (data?.strategy_id) {
                    fetch(`${API}/api/strategy/${data.strategy_id}`, { headers: getAuthHeaders() })
                        .then((response) => response.ok ? response.json() : null)
                        .then((strategyData) => {
                            if (strategyData) {
                                setStrategy({
                                    name: strategyData.name,
                                    timeframe: strategyData.timeframe,
                                    symbol: strategyData.symbol,
                                    symbols: strategyData.symbols,
                                })
                            }
                        })
                        .catch(() => setStrategy(null))
                }
            })
        fetch(`${API}/api/backtest/${id}/trades`).then(r => r.json()).then(setTrades)
    }, [id])

    const chartSymbol = useMemo(() => getChartSymbol(summary, strategy, trades), [summary, strategy, trades])
    const rawInterval = summary?.timeframe || strategy?.timeframe || '5min'
    const chartInterval = normalizeChartInterval(rawInterval)
    const chartTitle = `${chartSymbol} · ${formatTimeframe(rawInterval)}`

    if (!summary) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: T.textMuted, fontSize: 13 }}>⏳ Loading backtest results...</div>

    return (
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24, fontFamily: "'DM Sans', sans-serif" }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
                <div>
                    <button onClick={() => router.back()} style={{ background: 'none', border: 'none', color: T.textMuted, fontSize: 12, cursor: 'pointer', marginBottom: 4, padding: 0 }}>← Back</button>
                    <h1 style={{ fontSize: 22, fontWeight: 800, color: T.navy, margin: 0, letterSpacing: '-0.5px' }}>Backtest Results</h1>
                    <p style={{ fontSize: 13, color: T.textMuted, margin: '4px 0 0' }}>{summary.date_range} · {summary.candle_count?.toLocaleString() || '0'} candles</p>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                    <Link href="/strategy/new" style={{ padding: '9px 16px', border: `1px solid ${T.border}`, borderRadius: 8, background: '#fff', fontSize: 13, fontWeight: 600, color: T.textMid, textDecoration: 'none' }}>✏️ Modify</Link>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
                <Stat label="Total P&L" value={`Rs. ${fmtMoney(summary.total_pnl || 0)}`} color={summary.total_pnl >= 0 ? T.green : T.red} />
                <Stat label="Win Rate" value={`${summary.win_rate}%`} color={summary.win_rate >= 50 ? T.green : T.red} />
                <Stat label="Total Trades" value={String(summary.total_trades)} />
                <Stat label="Max Drawdown" value={`Rs. ${fmtMoney(summary.max_drawdown || 0)}`} color={T.red} />
                <Stat label="Avg Trade P&L" value={`Rs. ${fmtMoney(summary.avg_trade_pnl || 0)}`} color={summary.avg_trade_pnl >= 0 ? T.green : T.red} />
                <Stat label="Best Trade" value={`Rs. ${fmtMoney(summary.best_trade || 0)}`} color={T.green} />
                <Stat label="Worst Trade" value={`Rs. ${fmtMoney(summary.worst_trade || 0)}`} color={T.red} />
                <Stat label="Win / Loss" value={`${summary.winning_trades} / ${summary.losing_trades}`} />
            </div>

            <div style={{ marginBottom: 20, position: 'relative' }}>
                <BacktestChart backtestId={id} chartTitle={chartTitle} chartSymbol={chartSymbol} interval={chartInterval} />
            </div>

            <Card>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.textMid, letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 14 }}>All Trades ({trades.length})</div>
                {trades.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '32px 0', color: T.textMuted, fontSize: 13 }}>No trades executed — try adjusting entry conditions</div>
                ) : (
                    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                                {['#', 'Entry Time', 'Entry Rs.', 'Exit Time', 'Exit Rs.', 'P&L', 'P&L %', 'Exit Reason'].map(h => (
                                    <th key={h} style={{ textAlign: 'left', padding: '0 12px 10px 0', fontSize: 11, color: T.textMuted, fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase' }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {trades.map(t => (
                                <tr key={t.trade_no} style={{ borderBottom: `1px solid ${T.border}` }}>
                                    <td style={{ padding: '10px 12px 10px 0', color: T.textMuted }}>{t.trade_no}</td>
                                    <td style={{ padding: '10px 12px 10px 0', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>{new Date(t.entry_time).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}</td>
                                    <td style={{ padding: '10px 12px 10px 0', fontFamily: "'DM Mono', monospace" }}>Rs. {fmtMoney(t.entry_price)}</td>
                                    <td style={{ padding: '10px 12px 10px 0', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>{new Date(t.exit_time).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}</td>
                                    <td style={{ padding: '10px 12px 10px 0', fontFamily: "'DM Mono', monospace" }}>Rs. {fmtMoney(t.exit_price)}</td>
                                    <td style={{ padding: '10px 12px 10px 0', fontFamily: "'DM Mono', monospace", fontWeight: 700, color: t.pnl >= 0 ? T.green : T.red }}>Rs. {fmtMoney(t.pnl || 0)}</td>
                                    <td style={{ padding: '10px 12px 10px 0', color: t.pnl_pct >= 0 ? T.green : T.red, fontFamily: "'DM Mono', monospace" }}>{fmtPercent(t.pnl_pct || 0)}%</td>
                                    <td style={{ padding: '10px 0' }}>
                                        <span style={{
                                            fontSize: 11, padding: '2px 8px', borderRadius: 4, fontWeight: 700,
                                            background: t.exit_reason === 'TARGET' ? T.greenLight : t.exit_reason === 'SL' ? T.redLight : T.amberLight,
                                            color: t.exit_reason === 'TARGET' ? T.green : t.exit_reason === 'SL' ? T.red : T.amber,
                                        }}>{t.exit_reason}</span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </Card>
        </div>
    )
}
