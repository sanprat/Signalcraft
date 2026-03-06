'use client'

import { useState, useEffect } from 'react'
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

type BacktestSummary = {
    backtest_id: string
    strategy_id: string
    symbols?: string[]
    symbol?: string
    total_trades: number
    win_rate: number
    total_pnl: number
    date_range: string
    candle_count: number
}

function Card({ children, style = {} }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return <div style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`, boxShadow: '0 1px 3px rgba(0,0,0,0.04)', padding: 20, ...style }}>{children}</div>
}

export default function BacktestListPage() {
    const [backtests, setBacktests] = useState<BacktestSummary[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        fetch(`${API}/api/backtest`)
            .then(r => r.json())
            .then(data => {
                setBacktests(Array.isArray(data) ? data : [])
                setLoading(false)
            })
            .catch(err => {
                console.error('Failed to fetch backtests:', err)
                setLoading(false)
            })
    }, [])

    if (loading) {
        return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: T.textMuted, fontSize: 13 }}>⏳ Loading backtests...</div>
    }

    return (
        <div style={{ maxWidth: 1000, margin: '0 auto', padding: 24, fontFamily: "'DM Sans', sans-serif" }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                <div>
                    <h1 style={{ fontSize: 22, fontWeight: 800, color: T.navy, margin: 0, letterSpacing: '-0.5px' }}>Backtest History</h1>
                    <p style={{ fontSize: 13, color: T.textMuted, margin: '4px 0 0' }}>View and analyze your past strategy simulations.</p>
                </div>
                <Link href="/strategy/new" style={{ padding: '10px 20px', background: T.blue, color: '#fff', borderRadius: 8, fontSize: 13, fontWeight: 700, textDecoration: 'none' }}>
                    + New Strategy
                </Link>
            </div>

            {backtests.length === 0 ? (
                <Card style={{ textAlign: 'center', padding: '60px 20px' }}>
                    <div style={{ fontSize: 40, marginBottom: 16 }}>📊</div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: T.navy, marginBottom: 8 }}>No Backtests Found</h3>
                    <p style={{ fontSize: 13, color: T.textMuted, marginBottom: 24 }}>You haven't run any backtests yet. Start by building a strategy.</p>
                    <Link href="/strategy/new" style={{ color: T.blue, fontSize: 13, fontWeight: 600, textDecoration: 'none' }}>Build Strategy →</Link>
                </Card>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
                    {backtests.map(bt => (
                        <Link key={bt.backtest_id} href={`/backtest/${bt.backtest_id}`} style={{ textDecoration: 'none' }}>
                            <Card style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', transition: 'transform 0.1s', cursor: 'pointer' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                                    <div style={{
                                        width: 44, height: 44, borderRadius: 10, background: T.blueLight,
                                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18
                                    }}>
                                        ↩
                                    </div>
                                    <div>
                                        <div style={{ fontSize: 14, fontWeight: 700, color: T.navy }}>ID: {bt.backtest_id}</div>
                                        <div style={{ fontSize: 12, color: T.textMuted }}>{bt.date_range} · {bt.symbols?.join(', ') || bt.symbol || 'Equity'}</div>
                                    </div>
                                </div>

                                <div style={{ display: 'flex', gap: 32, alignItems: 'center' }}>
                                    <div style={{ textAlign: 'right' }}>
                                        <div style={{ fontSize: 10, color: T.textMuted, textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>Trades</div>
                                        <div style={{ fontSize: 14, fontWeight: 700, color: T.navy }}>{bt.total_trades}</div>
                                    </div>
                                    <div style={{ textAlign: 'right' }}>
                                        <div style={{ fontSize: 10, color: T.textMuted, textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>Win Rate</div>
                                        <div style={{ fontSize: 14, fontWeight: 700, color: bt.win_rate >= 50 ? T.green : T.red }}>{bt.win_rate}%</div>
                                    </div>
                                    <div style={{ textAlign: 'right', minWidth: 100 }}>
                                        <div style={{ fontSize: 10, color: T.textMuted, textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>Net P&L</div>
                                        <div style={{ fontSize: 14, fontWeight: 800, color: (bt.total_pnl || 0) >= 0 ? T.green : T.red }}>
                                            ₹{bt.total_pnl?.toLocaleString() || '0'}
                                        </div>
                                    </div>
                                    <div style={{ color: T.textMuted, fontSize: 18 }}>›</div>
                                </div>
                            </Card>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    )
}
