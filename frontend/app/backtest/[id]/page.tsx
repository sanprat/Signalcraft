'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { init, dispose, KLineData, Chart, DataLoader } from 'klinecharts'
import Link from 'next/link'
import { config } from '@/lib/config'

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
    backtest_id: string; strategy_id: string; total_trades: number
    winning_trades: number; losing_trades: number; win_rate: number
    total_pnl: number; max_drawdown: number; avg_trade_pnl: number
    best_trade: number; worst_trade: number; candle_count: number; date_range: string
}

type Trade = {
    trade_no: number; entry_time: string; entry_price: number
    exit_time: string; exit_price: number; pnl: number; pnl_pct: number; exit_reason: string
}

type HoveredTrade = {
    trade: Trade;
    x: number;
    y: number;
} | null

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

function KlineChart({ backtestId, trades }: { backtestId: string; trades: Trade[] }) {
    const containerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<Chart | null>(null)
    const [loaded, setLoaded] = useState(false)
    const [hoveredTrade, setHoveredTrade] = useState<HoveredTrade>(null)

    const candleDataRef = useRef<KLineData[]>([])

    const fetchCandleData = useCallback(async (): Promise<KLineData[]> => {
        let page = 0
        const allCandles: KLineData[] = []

        while (true) {
            const response = await fetch(`${API}/api/backtest/${backtestId}/candles?page=${page}&page_size=500`)
            const json = await response.json()

            const batch: KLineData[] = json.candles.time.map((t: number, i: number) => ({
                timestamp: t * 1000,
                open: json.candles.open[i],
                high: json.candles.high[i],
                low: json.candles.low[i],
                close: json.candles.close[i],
                volume: json.candles.volume?.[i] || 0,
            }))

            allCandles.push(...batch)

            if (allCandles.length >= json.total) break
            page++
        }

        return allCandles
    }, [backtestId])

    useEffect(() => {
        if (!backtestId || !containerRef.current) return

        const chart = init(containerRef.current)
        if (!chart) return

        chartRef.current = chart

        const dataLoader: DataLoader = {
            getBars: ({ callback }) => {
                const data = candleDataRef.current
                callback(data, false)
            },
            subscribeBar: ({ callback }) => {
                const data = candleDataRef.current
                if (data.length > 0) {
                    callback(data[data.length - 1])
                }
            },
        }

        chart.setDataLoader(dataLoader)

        fetchCandleData().then((data) => {
            candleDataRef.current = data
            chart.setDataLoader(dataLoader)
            setLoaded(true)
        })

        return () => {
            dispose(containerRef.current!)
        }
    }, [backtestId, fetchCandleData])

    useEffect(() => {
        if (!chartRef.current || !loaded || !trades.length || !candleDataRef.current.length) return

        const chart = chartRef.current

        trades.forEach(trade => {
            const entryTime = new Date(trade.entry_time).getTime()
            const exitTime = new Date(trade.exit_time).getTime()

            chart.createOverlay({
                name: 'simpleAnnotation',
                points: [{ timestamp: entryTime, value: trade.entry_price }],
                extendData: '▲ BUY',
                styles: {
                    line: { color: T.green },
                    text: { color: T.green, backgroundColor: T.greenLight },
                },
                lock: true,
            })

            chart.createOverlay({
                name: 'simpleAnnotation',
                points: [{ timestamp: exitTime, value: trade.exit_price }],
                extendData: '▼ SELL',
                styles: {
                    line: { color: T.red },
                    text: { color: T.red, backgroundColor: T.redLight },
                },
                lock: true,
            })
        })

        chart.subscribeAction('onCrosshairChange', (params) => {
            if (!params || !trades.length) {
                setHoveredTrade(null)
                return
            }

            const crosshair = params as { timestamp?: number; x?: number; y?: number }
            if (!crosshair.timestamp) {
                setHoveredTrade(null)
                return
            }

            const timestamp = crosshair.timestamp

            const matchingTrade = trades.find(trade => {
                const entryTime = new Date(trade.entry_time).getTime()
                const exitTime = new Date(trade.exit_time).getTime()
                return timestamp >= entryTime && timestamp <= exitTime
            })

            if (matchingTrade && crosshair.x !== undefined && crosshair.y !== undefined) {
                setHoveredTrade({
                    trade: matchingTrade,
                    x: crosshair.x,
                    y: crosshair.y,
                })
            } else {
                setHoveredTrade(null)
            }
        })
    }, [loaded, trades])

    return (
        <Card>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: T.navy }}>Price Chart</span>
                <div style={{ display: 'flex', gap: 8 }}>
                    <span style={{ fontSize: 11, color: T.green }}>▲ Entry</span>
                    <span style={{ fontSize: 11, color: T.red }}>▼ Exit</span>
                </div>
            </div>
            <div ref={containerRef} style={{ height: 400, borderRadius: 8, overflow: 'hidden', position: 'relative' }} />
            {hoveredTrade && (
                <div style={{
                    position: 'absolute',
                    left: Math.min(hoveredTrade.x + 10, 600),
                    top: hoveredTrade.y - 80,
                    background: T.surface,
                    border: `1px solid ${T.border}`,
                    borderRadius: 8,
                    padding: '10px 14px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                    zIndex: 100,
                    fontSize: 12,
                    minWidth: 180,
                }}>
                    <div style={{ fontWeight: 700, marginBottom: 6, color: T.navy }}>
                        Trade #{hoveredTrade.trade.trade_no}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
                        <span style={{ color: T.textMuted }}>Entry:</span>
                        <span style={{ fontFamily: "'DM Mono', monospace", color: T.green }}>Rs. {hoveredTrade.trade.entry_price}</span>
                        <span style={{ color: T.textMuted }}>Exit:</span>
                        <span style={{ fontFamily: "'DM Mono', monospace", color: T.red }}>Rs. {hoveredTrade.trade.exit_price}</span>
                        <span style={{ color: T.textMuted }}>P&L:</span>
                        <span style={{ fontFamily: "'DM Mono', monospace", fontWeight: 700, color: hoveredTrade.trade.pnl >= 0 ? T.green : T.red }}>
                            Rs. {hoveredTrade.trade.pnl?.toLocaleString()} ({hoveredTrade.trade.pnl_pct}%)
                        </span>
                        <span style={{ color: T.textMuted }}>Reason:</span>
                        <span style={{
                            fontSize: 10, padding: '2px 6px', borderRadius: 4, fontWeight: 700,
                            background: hoveredTrade.trade.exit_reason === 'TARGET' ? T.greenLight : hoveredTrade.trade.exit_reason === 'SL' ? T.redLight : T.amberLight,
                            color: hoveredTrade.trade.exit_reason === 'TARGET' ? T.green : hoveredTrade.trade.exit_reason === 'SL' ? T.red : T.amber,
                        }}>
                            {hoveredTrade.trade.exit_reason}
                        </span>
                    </div>
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

    useEffect(() => {
        if (!id) return
        fetch(`${API}/api/backtest/${id}/summary`).then(r => r.json()).then(setSummary)
        fetch(`${API}/api/backtest/${id}/trades`).then(r => r.json()).then(setTrades)
    }, [id])

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
                <Stat label="Total P&L" value={`Rs. ${summary.total_pnl?.toLocaleString() || '0'}`} color={summary.total_pnl >= 0 ? T.green : T.red} />
                <Stat label="Win Rate" value={`${summary.win_rate}%`} color={summary.win_rate >= 50 ? T.green : T.red} />
                <Stat label="Total Trades" value={String(summary.total_trades)} />
                <Stat label="Max Drawdown" value={`Rs. ${summary.max_drawdown?.toLocaleString() || '0'}`} color={T.red} />
                <Stat label="Avg Trade P&L" value={`Rs. ${summary.avg_trade_pnl?.toLocaleString() || '0'}`} color={summary.avg_trade_pnl >= 0 ? T.green : T.red} />
                <Stat label="Best Trade" value={`Rs. ${summary.best_trade?.toLocaleString() || '0'}`} color={T.green} />
                <Stat label="Worst Trade" value={`Rs. ${summary.worst_trade?.toLocaleString() || '0'}`} color={T.red} />
                <Stat label="Win / Loss" value={`${summary.winning_trades} / ${summary.losing_trades}`} />
            </div>

            <div style={{ marginBottom: 20, position: 'relative' }}>
                <KlineChart backtestId={id} trades={trades} />
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
                                    <td style={{ padding: '10px 12px 10px 0', fontFamily: "'DM Mono', monospace" }}>Rs. {t.entry_price}</td>
                                    <td style={{ padding: '10px 12px 10px 0', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>{new Date(t.exit_time).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}</td>
                                    <td style={{ padding: '10px 12px 10px 0', fontFamily: "'DM Mono', monospace" }}>Rs. {t.exit_price}</td>
                                    <td style={{ padding: '10px 12px 10px 0', fontFamily: "'DM Mono', monospace", fontWeight: 700, color: t.pnl >= 0 ? T.green : T.red }}>Rs. {t.pnl?.toLocaleString() || '0'}</td>
                                    <td style={{ padding: '10px 12px 10px 0', color: t.pnl_pct >= 0 ? T.green : T.red, fontFamily: "'DM Mono', monospace" }}>{t.pnl_pct}%</td>
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
