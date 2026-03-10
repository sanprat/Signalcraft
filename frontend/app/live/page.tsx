'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useQuotes } from '@/hooks/useQuotes'
import { config } from '@/lib/config'
import { BackButton } from '@/components/BackButton'

const API = config.apiBaseUrl

const T = {
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF', blueMid: '#BFDBFE',
    green: '#059669', greenLight: '#ECFDF5', greenMid: '#A7F3D0',
    red: '#DC2626', redLight: '#FEF2F2', redMid: '#FECACA',
    amber: '#D97706', amberLight: '#FFFBEB',
    text: '#0F172A', textMid: '#475569', textMuted: '#94A3B8',
    border: '#E2E8F0', borderStrong: '#CBD5E1', surface: '#FFFFFF', bg: '#F8FAFC',
}

function Card({ children, style = {} }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return <div style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`, boxShadow: '0 1px 3px rgba(0,0,0,0.04)', padding: 20, ...style }}>{children}</div>
}

function StatusPill({ status }: { status: string }) {
    const map: Record<string, { label: string; bg: string; fg: string }> = {
        ACTIVE: { label: '● LIVE', bg: T.greenLight, fg: T.green },
        PAPER: { label: '◎ PAPER', bg: T.blueLight, fg: T.blue },
        PAUSED: { label: '⏸ PAUSED', bg: T.amberLight, fg: T.amber },
        STOPPED: { label: '■ STOPPED', bg: T.redLight, fg: T.red },
    }
    const s = map[status] || { label: status, bg: T.bg, fg: T.textMuted }
    return <span style={{ background: s.bg, color: s.fg, borderRadius: 20, padding: '2px 9px', fontSize: 11, fontWeight: 700, letterSpacing: '0.5px', fontFamily: "'DM Mono', monospace" }}>{s.label}</span>
}

function PnlBadge({ val, pct }: { val: number; pct: number }) {
    const pos = val >= 0
    return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, background: pos ? T.greenLight : T.redLight, color: pos ? T.green : T.red, borderRadius: 6, padding: '3px 8px', fontWeight: 600, fontSize: 13, fontFamily: "'DM Mono', monospace" }}>
            {pos ? '▲' : '▼'} Rs. {Math.abs(val).toLocaleString()} <span style={{ opacity: 0.7, fontSize: 11 }}>({pos ? '+' : ''}{pct.toFixed(2)}%)</span>
        </span>
    )
}

export default function LiveTradingPage() {
    const [strategies, setStrategies] = useState<any[]>([])
    const [positions, setPositions] = useState<any[]>([])
    const [analytics, setAnalytics] = useState<any>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const { quotes, marketOpen } = useQuotes()

    // 1. Fetch data on load
    useEffect(() => {
        const fetchData = async () => {
            try {
                const fetchOptions = { credentials: 'include' as const }
                const [stratsRes, posRes, anaRes] = await Promise.all([
                    fetch(`${API}/api/live/strategies`, fetchOptions),
                    fetch(`${API}/api/live/positions`, fetchOptions),
                    fetch(`${API}/api/live/analytics`, fetchOptions)
                ])
                
                // Check if responses are OK
                if (!stratsRes.ok || !posRes.ok || !anaRes.ok) {
                    if (stratsRes.status === 401 || posRes.status === 401 || anaRes.status === 401) {
                        setError('Please log in to view live trading data')
                    } else {
                        setError('Failed to fetch live trading data')
                    }
                    setLoading(false)
                    return
                }
                
                const strats = await stratsRes.json()
                const pos = await posRes.json()
                const ana = await anaRes.json()
                
                // Ensure arrays
                setStrategies(Array.isArray(strats) ? strats : [])
                setPositions(Array.isArray(pos) ? pos : [])
                setAnalytics(ana)
                setError(null)
            } catch (err) {
                console.error("Failed to fetch live data", err)
                setError('Network error. Please check your connection.')
            } finally {
                setLoading(false)
            }
        }
        fetchData()
        const interval = setInterval(fetchData, 10000)
        return () => clearInterval(interval)
    }, [])

    const openPositions = positions.filter(p => p.status === 'OPEN')
    const closedPositions = positions.filter(p => p.status === 'CLOSED')

    // 2. Real-time P&L calculation
    const calculatedPositions = openPositions.map(p => {
        const quote = quotes[p.symbol]
        const ltp = quote ? quote.ltp : p.entry_price
        const pnl = (ltp - p.entry_price) * p.quantity
        const pnlPct = (pnl / (p.entry_price * p.quantity)) * 100
        return { ...p, current_price: ltp, live_pnl: pnl, live_pnl_pct: pnlPct }
    })

    const totalOpenPnl = calculatedPositions.reduce((a, p) => a + p.live_pnl, 0)
    const totalClosedPnl = closedPositions.reduce((a, p) => a + (p.pnl || 0), 0)
    const totalTodayPnl = totalOpenPnl + totalClosedPnl

    const toggleStatus = async (liveId: number, currentStatus: string) => {
        let nextStatus = 'ACTIVE'
        if (currentStatus === 'ACTIVE') nextStatus = 'PAUSED'
        else if (currentStatus === 'PAUSED') nextStatus = 'ACTIVE'
        else if (currentStatus === 'STOPPED') nextStatus = 'ACTIVE'

        setStrategies(prev => prev.map(s => s.id === liveId ? { ...s, status: nextStatus } : s))
        try {
            await fetch(`${API}/api/live/toggle/${liveId}?status=${nextStatus}`, { 
                method: 'POST',
                credentials: 'include'
            })
        } catch (err) {
            console.error("Failed to toggle status", err)
        }
    }

    const stopStrategy = async (liveId: number) => {
        if (!confirm("Are you sure you want to stop this strategy? This will stop signal monitoring.")) return
        setStrategies(prev => prev.map(s => s.id === liveId ? { ...s, status: 'STOPPED' } : s))
        try {
            await fetch(`${API}/api/live/stop/${liveId}`, { 
                method: 'POST',
                credentials: 'include'
            })
        } catch (err) {
            console.error("Failed to stop strategy", err)
        }
    }

    const deleteStrategy = async (liveId: number) => {
        if (!confirm("Permanently remove this strategy from the dashboard?")) return
        setStrategies(prev => prev.filter(s => s.id !== liveId))
        try {
            await fetch(`${API}/api/live/strategy/${liveId}`, { 
                method: 'DELETE',
                credentials: 'include'
            })
        } catch (err) {
            console.error("Failed to delete strategy", err)
        }
    }

    if (loading && strategies.length === 0) {
        return <div style={{ padding: 40, textAlign: 'center', color: T.textMuted }}>Loading Live Dashboard...</div>
    }

    if (error) {
        return (
            <div style={{ padding: 40, textAlign: 'center' }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>🔒</div>
                <h2 style={{ color: T.navy, marginBottom: 8 }}>Access Required</h2>
                <p style={{ color: T.textMuted, marginBottom: 24 }}>{error}</p>
                <Link href="/login" style={{ padding: '10px 20px', background: T.blue, color: '#fff', borderRadius: 8, textDecoration: 'none', fontWeight: 600 }}>
                    Go to Login
                </Link>
            </div>
        )
    }

    return (
        <div style={{ padding: 24, fontFamily: "'DM Sans', sans-serif", background: T.bg, minHeight: '100vh' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <BackButton defaultBack="/dashboard" />
                    <div>
                        <h1 style={{ fontSize: 24, fontWeight: 800, color: T.navy, letterSpacing: '-0.5px', margin: 0 }}>Live Trading Dashboard</h1>
                        <p style={{ fontSize: 13, color: T.textMuted, marginTop: 4 }}>
                            {strategies.filter(s => s.status === 'ACTIVE' || s.status === 'PAPER').length} active · {strategies.length} total strategies
                        </p>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: 12 }}>
                    <div style={{ padding: '8px 16px', background: '#fff', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: analytics?.telegram_enabled ? T.green : T.red }}></span>
                        <span style={{ fontWeight: 600, color: T.textMid }}>Telegram Notifications: {analytics?.telegram_enabled ? 'Connected' : 'Not Configured'}</span>
                    </div>
                    <Link href="/strategy/new" style={{ padding: '10px 18px', background: T.blue, color: '#fff', borderRadius: 8, fontSize: 13, fontWeight: 700, textDecoration: 'none', transition: 'opacity 0.2s' }}>⚡ Deploy New Strategy</Link>
                </div>
            </div>

            {/* Performance & Charts */}
            <div style={{ display: 'grid', gridTemplateColumns: '7fr 3fr', gap: 24, marginBottom: 32 }}>
                <Card style={{ padding: 24 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                        <h3 style={{ fontSize: 16, fontWeight: 700, color: T.navy, margin: 0 }}>📈 Equity Curve (Realized P&L)</h3>
                        <div style={{ fontSize: 12, color: T.textMuted, fontWeight: 600 }}>Total Realized: <span style={{ color: totalClosedPnl >= 0 ? T.green : T.red }}>₹{totalClosedPnl.toLocaleString()}</span></div>
                    </div>
                    <div style={{ height: 200, display: 'flex', alignItems: 'flex-end', gap: 4, background: T.bg, borderRadius: 8, padding: '10px 20px', border: `1px solid ${T.border}` }}>
                        {analytics?.equity_curve?.length > 0 ? (
                            analytics.equity_curve.map((p: any, i: number) => {
                                const max = Math.max(...analytics.equity_curve.map((x: any) => Math.abs(x.pnl)), 1000)
                                const height = (Math.abs(p.pnl) / max) * 150
                                return (
                                    <div key={i} style={{ flex: 1, height: height, background: p.pnl >= 0 ? T.green : T.red, opacity: 0.8, borderRadius: '2px 2px 0 0', position: 'relative' }} title={`₹${p.pnl.toFixed(2)}`}>
                                    </div>
                                )
                            })
                        ) : (
                            <div style={{ width: '100%', textAlign: 'center', paddingBottom: 80, color: T.textMuted, fontSize: 13 }}>No realized trades for charting.</div>
                        )}
                    </div>
                </Card>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <Card style={{ padding: 20 }}>
                        <div style={{ fontSize: 11, color: T.textMuted, fontWeight: 700, letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 12 }}>Daily Risk Monitor</div>
                        {analytics?.risk_status?.map((rs: any) => (
                            <div key={rs.id} style={{ marginBottom: 14, paddingBottom: 10, borderBottom: `1px solid ${T.bg}` }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 700, color: T.navy, marginBottom: 6 }}>
                                    <span>{rs.name}</span>
                                    <span style={{ color: rs.is_active ? T.green : T.red }}>{rs.is_active ? '● Safe' : '■ Stopped'}</span>
                                </div>
                                <div style={{ height: 4, background: T.bg, borderRadius: 2, overflow: 'hidden', marginBottom: 6 }}>
                                    <div style={{ width: `${Math.min((rs.trades_today / rs.max_trades) * 100, 100)}%`, height: '100%', background: T.blue }}></div>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: T.textMuted }}>
                                    <span>Trades: {rs.trades_today}/{rs.max_trades}</span>
                                    <span>Loss: <span style={{ color: rs.pnl_today < 0 ? T.red : T.textMuted }}>₹{Math.abs(rs.pnl_today)}</span>/₹{rs.max_loss}</span>
                                </div>
                            </div>
                        ))}
                    </Card>
                    <Card style={{ padding: 20, background: T.blue, color: '#fff' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, opacity: 0.8, textTransform: 'uppercase', marginBottom: 8 }}>Today's Performance</div>
                        <div style={{ fontSize: 28, fontWeight: 900, fontFamily: "'DM Mono', monospace" }}>
                            {totalTodayPnl >= 0 ? '+' : '-'}₹{Math.abs(totalTodayPnl).toLocaleString()}
                        </div>
                        <div style={{ fontSize: 12, marginTop: 4, opacity: 0.9 }}>
                            Net returns across {openPositions.length} active trades
                        </div>
                    </Card>
                </div>
            </div>

            {/* Strategies Section */}
            <section style={{ marginBottom: 40 }}>
                <h2 style={{ fontSize: 18, fontWeight: 800, color: T.navy, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
                    🚀 Live Strategies
                    <span style={{ fontSize: 12, fontWeight: 600, color: T.textMuted, background: '#fff', padding: '2px 8px', borderRadius: 12, border: `1px solid ${T.border}` }}>{strategies.length}</span>
                </h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 20 }}>
                    {strategies.map(strat => (
                        <Card key={strat.id} style={{ borderLeft: `4px solid ${strat.status === 'ACTIVE' ? T.green : strat.status === 'PAPER' ? T.blue : strat.status === 'PAUSED' ? T.amber : T.red}` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                                <div>
                                    <h3 style={{ fontSize: 16, fontWeight: 700, color: T.navy, margin: 0 }}>{strat.name}</h3>
                                    <div style={{ display: 'flex', gap: 6, marginTop: 6, alignItems: 'center' }}>
                                        <StatusPill status={strat.status} />
                                        <span style={{ fontSize: 11, color: T.textMuted, fontWeight: 600, background: T.bg, padding: '2px 6px', borderRadius: 4 }}>{strat.broker.toUpperCase()}</span>
                                    </div>
                                </div>
                                <div style={{ display: 'flex', gap: 6 }}>
                                    {strat.status !== 'STOPPED' && (
                                        <button onClick={() => toggleStatus(strat.id, strat.status)} style={{ padding: '6px', borderRadius: 6, border: `1px solid ${T.border}`, background: '#fff', cursor: 'pointer', display: 'flex' }}>
                                            {strat.status === 'PAUSED' ? '▶️' : '⏸️'}
                                        </button>
                                    )}
                                    {strat.status !== 'STOPPED' ? (
                                        <button onClick={() => stopStrategy(strat.id)} style={{ padding: '6px', borderRadius: 6, border: `1px solid ${T.redMid}`, background: T.redLight, color: T.red, cursor: 'pointer', display: 'flex' }}>⏹️</button>
                                    ) : (
                                        <button onClick={() => deleteStrategy(strat.id)} style={{ padding: '6px', borderRadius: 6, border: `1px solid ${T.border}`, background: '#fff', color: T.textMuted, cursor: 'pointer', display: 'flex' }} title="Remove from Dashboard">🗑️</button>
                                    )}
                                </div>
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                {(() => {
                                    try {
                                        const parsed = JSON.parse(strat.symbols || '[]');
                                        const symbolArray = Array.isArray(parsed) ? parsed : [parsed];
                                        return symbolArray.map((s: string) => (
                                            <span key={s} style={{ fontSize: 11, fontWeight: 600, color: T.blue, background: T.blueLight, padding: '2px 8px', borderRadius: 4, fontFamily: "'DM Mono', monospace" }}>{s}</span>
                                        ));
                                    } catch (e) {
                                        return <span style={{ fontSize: 11, fontWeight: 600, color: T.blue, background: T.blueLight, padding: '2px 8px', borderRadius: 4 }}>{strat.symbols}</span>;
                                    }
                                })()}
                            </div>
                        </Card>
                    ))}
                    {strategies.length === 0 && (
                        <div style={{ gridColumn: '1/-1', padding: '60px 20px', textAlign: 'center', background: '#fff', borderRadius: 12, border: `2px dashed ${T.border}` }}>
                            <div style={{ fontSize: 40, marginBottom: 16 }}>📊</div>
                            <h3 style={{ fontSize: 18, color: T.navy, margin: '0 0 8px' }}>No strategies deployed</h3>
                            <p style={{ color: T.textMuted, margin: 0 }}>Go to the Strategy Builder to deploy your first live strategy.</p>
                        </div>
                    )}
                </div>
            </section>

            {/* Positions Section */}
            <section style={{ marginBottom: 40 }}>
                <h2 style={{ fontSize: 18, fontWeight: 800, color: T.navy, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
                    📌 Open Positions
                    {openPositions.length > 0 && <span style={{ fontSize: 12, fontWeight: 600, color: '#fff', background: T.blue, padding: '2px 8px', borderRadius: 12 }}>{openPositions.length}</span>}
                </h2>
                <Card style={{ padding: 0, overflow: 'hidden' }}>
                    {calculatedPositions.length > 0 ? (
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead style={{ background: T.bg, borderBottom: `1px solid ${T.border}` }}>
                                    <tr>
                                        {['Symbol', 'Qty', 'Avg. Entry', 'LTP', 'PnL', 'Status', 'Actions'].map(h => (
                                            <th key={h} style={{ padding: '14px 20px', fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.8px', textAlign: 'left' }}>{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {calculatedPositions.map(pos => (
                                        <tr key={pos.id} style={{ borderBottom: `1px solid ${T.border}`, transition: 'background 0.2s' }}>
                                            <td style={{ padding: '16px 20px', fontSize: 15, fontWeight: 800, color: T.navy, fontFamily: "'DM Mono', monospace" }}>{pos.symbol}</td>
                                            <td style={{ padding: '16px 20px', fontSize: 14, fontWeight: 500 }}>{pos.quantity}</td>
                                            <td style={{ padding: '16px 20px', fontSize: 14, color: T.textMid }}>₹{pos.entry_price.toLocaleString()}</td>
                                            <td style={{ padding: '16px 20px', fontSize: 14, fontWeight: 700, color: T.navy }}>₹{pos.current_price.toLocaleString()}</td>
                                            <td style={{ padding: '16px 20px' }}>
                                                <PnlBadge val={pos.live_pnl} pct={pos.live_pnl_pct} />
                                            </td>
                                            <td style={{ padding: '16px 20px' }}><StatusPill status={pos.status} /></td>
                                            <td style={{ padding: '16px 20px' }}>
                                                <button style={{ background: 'none', border: `1px solid ${T.redMid}`, color: T.red, padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>Exit</button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div style={{ padding: '60px 20px', textAlign: 'center' }}>
                            <p style={{ margin: 0, color: T.textMuted, fontWeight: 500 }}>No active trades currently. Waiting for signals...</p>
                        </div>
                    )}
                </Card>
            </section>

            {/* History Section */}
            <section>
                <h2 style={{ fontSize: 18, fontWeight: 800, color: T.navy, marginBottom: 16 }}>📜 Trade History (Today)</h2>
                <Card style={{ padding: 0, overflow: 'hidden' }}>
                    {closedPositions.length > 0 ? (
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead style={{ background: T.bg, borderBottom: `1px solid ${T.border}` }}>
                                    <tr>
                                        {['Symbol', 'Exit Reason', 'Entry', 'Exit', 'Net PnL', 'Time'].map(h => (
                                            <th key={h} style={{ padding: '14px 20px', fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.8px', textAlign: 'left' }}>{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {closedPositions.map(pos => (
                                        <tr key={pos.id} style={{ borderBottom: `1px solid ${T.border}` }}>
                                            <td style={{ padding: '14px 20px', fontSize: 14, fontWeight: 700, color: T.navy, fontFamily: "'DM Mono', monospace" }}>{pos.symbol}</td>
                                            <td style={{ padding: '14px 20px', fontSize: 12, color: T.textMid }}><span style={{ background: T.bg, padding: '2px 6px', borderRadius: 4, fontWeight: 600 }}>{pos.exit_reason || 'MANUAL'}</span></td>
                                            <td style={{ padding: '14px 20px', fontSize: 13, color: T.textMuted }}>₹{pos.entry_price.toLocaleString()}</td>
                                            <td style={{ padding: '14px 20px', fontSize: 13, color: T.textMid, fontWeight: 600 }}>₹{pos.exit_price?.toLocaleString()}</td>
                                            <td style={{ padding: '14px 20px' }}>
                                                <PnlBadge val={pos.pnl || 0} pct={pos.pnl_pct || 0} />
                                            </td>
                                            <td style={{ padding: '14px 20px', fontSize: 12, color: T.textMuted }}>{pos.exit_time ? new Date(pos.exit_time).toLocaleTimeString() : '-'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div style={{ padding: '40px 20px', textAlign: 'center' }}>
                            <p style={{ margin: 0, color: T.textMuted, fontSize: 13 }}>No trades completed today.</p>
                        </div>
                    )}
                </Card>
            </section>
        </div>
    )
}
