'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { createChart, IChartApi, ISeriesApi, CandlestickData, Time } from 'lightweight-charts'
import { useRef } from 'react'
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

function CandleChart({ backtestId }: { backtestId: string }) {
    const ref = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
    const [all, setAll] = useState<CandlestickData[]>([])
    const [idx, setIdx] = useState(100)
    const [playing, setPlaying] = useState(false)
    const [speed, setSpeed] = useState(1)
    const [loaded, setLoaded] = useState(false)

    useEffect(() => {
        if (!backtestId) return
            ; (async () => {
                let page = 0, result: CandlestickData[] = []
                while (true) {
                    const r = await fetch(`${API}/api/backtest/${backtestId}/candles?page=${page}&page_size=500`)
                    const j = await r.json()
                    const batch = j.candles.time.map((t: number, i: number) => ({
                        time: t as Time, open: j.candles.open[i], high: j.candles.high[i], low: j.candles.low[i], close: j.candles.close[i],
                    }))
                    result = [...result, ...batch]
                    if (result.length >= j.total) break
                    page++
                }
                setAll(result); setLoaded(true)
            })()
    }, [backtestId])

    useEffect(() => {
        if (!ref.current || !loaded || !all.length) return
        const chart = createChart(ref.current, {
            width: ref.current.clientWidth, height: 380,
            layout: { background: { color: '#FFFFFF' }, textColor: '#94A3B8' },
            grid: { vertLines: { color: '#F1F5F9' }, horzLines: { color: '#F1F5F9' } },
            crosshair: { mode: 1 },
            rightPriceScale: { borderColor: '#E2E8F0' },
            timeScale: { borderColor: '#E2E8F0', timeVisible: true },
        })
        const series = chart.addCandlestickSeries({
            upColor: T.green, downColor: T.red,
            borderUpColor: T.green, borderDownColor: T.red,
            wickUpColor: T.green, wickDownColor: T.red,
        })
        chartRef.current = chart; seriesRef.current = series
        series.setData(all.slice(0, 100))
        return () => chart.remove()
    }, [loaded, all])

    useEffect(() => {
        if (!playing || idx >= all.length) { setPlaying(false); return }
        const timer = setInterval(() => {
            setIdx(i => {
                const next = Math.min(i + speed, all.length)
                seriesRef.current?.setData(all.slice(0, next))
                if (next >= all.length) setPlaying(false)
                return next
            })
        }, 300)
        return () => clearInterval(timer)
    }, [playing, speed, idx, all])

    const pct = all.length ? Math.round((idx / all.length) * 100) : 0

    return (
        <Card>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: T.navy }}>Candle Replay</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, color: T.textMuted, fontFamily: "'DM Mono', monospace" }}>{idx}/{all.length}</span>
                    <select value={speed} onChange={e => setSpeed(Number(e.target.value))}
                        style={{ padding: '4px 8px', border: `1px solid ${T.border}`, borderRadius: 6, fontSize: 12, fontFamily: "'DM Sans', sans-serif" }}>
                        {[1, 5, 10, 50].map(s => <option key={s} value={s}>{s}×</option>)}
                    </select>
                    <button onClick={() => { seriesRef.current?.setData(all.slice(0, 100)); setIdx(100); setPlaying(false) }}
                        style={{ padding: '5px 10px', border: `1px solid ${T.border}`, borderRadius: 6, background: '#fff', fontSize: 11, fontWeight: 600, cursor: 'pointer', color: T.textMid }}>⟳ Reset</button>
                    <button onClick={() => setPlaying(p => !p)} disabled={!loaded}
                        style={{ padding: '5px 14px', border: 'none', background: playing ? T.redLight : T.blue, color: playing ? T.red : '#fff', borderRadius: 6, fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>
                        {!loaded ? '⏳ Loading...' : playing ? '⏸ Pause' : '▶ Play'}
                    </button>
                </div>
            </div>
            <div style={{ height: 4, background: T.bg, borderRadius: 2, marginBottom: 10 }}>
                <div style={{ height: 4, background: T.blue, borderRadius: 2, width: `${pct}%`, transition: 'width 0.3s' }} />
            </div>
            <div ref={ref} style={{ borderRadius: 8, overflow: 'hidden' }} />
        </Card>
    )
}

export default function BacktestResultsPage() {
    const { id } = useParams() as { id: string }
    const router = useRouter()
    const [summary, setSummary] = useState<Summary | null>(null)
    const [trades, setTrades] = useState<Trade[]>([])
    const [deploying, setDeploying] = useState(false)
    const [deployed, setDeployed] = useState(false)
    const [deployModal, setDeployModal] = useState(false)
    const [broker, setBroker] = useState('shoonya')

    useEffect(() => {
        if (!id) return
        fetch(`${API}/api/backtest/${id}/summary`).then(r => r.json()).then(setSummary)
        fetch(`${API}/api/backtest/${id}/trades`).then(r => r.json()).then(setTrades)
    }, [id])

    const deployLive = async () => {
        setDeploying(true)
        try {
            await fetch(`${API}/api/live/deploy`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ strategy_id: summary?.strategy_id, broker, paper: false }),
            })
            setDeployed(true)
        } catch { }
        setDeploying(false)
        setDeployModal(false)
    }

    if (!summary) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: T.textMuted, fontSize: 13 }}>⏳ Loading backtest results...</div>

    return (
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24, fontFamily: "'DM Sans', sans-serif" }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
                <div>
                    <button onClick={() => router.back()} style={{ background: 'none', border: 'none', color: T.textMuted, fontSize: 12, cursor: 'pointer', marginBottom: 4, padding: 0 }}>← Back</button>
                    <h1 style={{ fontSize: 22, fontWeight: 800, color: T.navy, margin: 0, letterSpacing: '-0.5px' }}>Backtest Results</h1>
                    <p style={{ fontSize: 13, color: T.textMuted, margin: '4px 0 0' }}>{summary.date_range} · {summary.candle_count.toLocaleString()} candles</p>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                    <Link href="/strategy/new" style={{ padding: '9px 16px', border: `1px solid ${T.border}`, borderRadius: 8, background: '#fff', fontSize: 13, fontWeight: 600, color: T.textMid, textDecoration: 'none' }}>✏️ Modify</Link>
                    {deployed ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px', background: T.greenLight, border: `1px solid ${T.greenMid}`, borderRadius: 8 }}>
                            <span style={{ width: 7, height: 7, borderRadius: '50%', background: T.green, display: 'inline-block' }} />
                            <span style={{ fontSize: 13, fontWeight: 700, color: T.green }}>Live — Trading Active</span>
                        </div>
                    ) : (
                        <button onClick={() => setDeployModal(true)} style={{ padding: '9px 18px', background: T.blue, color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>
                            ◉ Deploy Live
                        </button>
                    )}
                </div>
            </div>

            {/* Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
                <Stat label="Total P&L" value={`Rs. ${summary.total_pnl.toLocaleString()}`} color={summary.total_pnl >= 0 ? T.green : T.red} />
                <Stat label="Win Rate" value={`${summary.win_rate}%`} color={summary.win_rate >= 50 ? T.green : T.red} />
                <Stat label="Total Trades" value={String(summary.total_trades)} />
                <Stat label="Max Drawdown" value={`Rs. ${summary.max_drawdown.toLocaleString()}`} color={T.red} />
                <Stat label="Avg Trade P&L" value={`Rs. ${summary.avg_trade_pnl.toLocaleString()}`} color={summary.avg_trade_pnl >= 0 ? T.green : T.red} />
                <Stat label="Best Trade" value={`Rs. ${summary.best_trade.toLocaleString()}`} color={T.green} />
                <Stat label="Worst Trade" value={`Rs. ${summary.worst_trade.toLocaleString()}`} color={T.red} />
                <Stat label="Win / Loss" value={`${summary.winning_trades} / ${summary.losing_trades}`} />
            </div>

            {/* Chart */}
            <div style={{ marginBottom: 20 }}>
                <CandleChart backtestId={id} />
            </div>

            {/* Trade table */}
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
                                    <td style={{ padding: '10px 12px 10px 0', fontFamily: "'DM Mono', monospace", fontWeight: 700, color: t.pnl >= 0 ? T.green : T.red }}>Rs. {t.pnl.toLocaleString()}</td>
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

            {/* Deploy modal */}
            {deployModal && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
                    <div style={{ background: '#fff', borderRadius: 16, padding: 32, maxWidth: 400, width: '90%', boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
                        <h2 style={{ fontSize: 18, fontWeight: 800, color: T.navy, margin: '0 0 6px' }}>Deploy Live</h2>
                        <p style={{ fontSize: 13, color: T.textMuted, margin: '0 0 20px' }}>Select broker to deploy this strategy</p>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 24 }}>
                            {['shoonya', 'zerodha', 'flattrade', 'dhan'].map(b => (
                                <button key={b} onClick={() => setBroker(b)} style={{
                                    padding: 12, border: `2px solid ${broker === b ? T.blue : T.border}`,
                                    borderRadius: 8, background: broker === b ? T.blueLight : '#fff',
                                    color: broker === b ? T.blue : T.textMid, fontSize: 13, fontWeight: 600, cursor: 'pointer', textTransform: 'capitalize',
                                }}>{b}</button>
                            ))}
                        </div>
                        <div style={{ display: 'flex', gap: 10 }}>
                            <button onClick={() => setDeployModal(false)} style={{ flex: 1, padding: 12, border: `1px solid ${T.border}`, borderRadius: 8, background: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', color: T.textMid }}>Cancel</button>
                            <button onClick={deployLive} disabled={deploying} style={{ flex: 1, padding: 12, border: 'none', background: T.blue, borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer', color: '#fff' }}>
                                {deploying ? 'Deploying...' : `◉ Go Live via ${broker}`}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
