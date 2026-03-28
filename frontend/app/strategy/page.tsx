'use client'

import { useState, useEffect, Suspense } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { config } from '@/lib/config'
import { AppShell } from '@/components/AppShell'
import { loadStrategy, backtestStrategy } from '@/lib/api/strategy'

const T = {
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF', blueMid: '#BFDBFE',
    green: '#059669', greenLight: '#ECFDF5', greenMid: '#A7F3D0',
    red: '#DC2626', redLight: '#FEF2F2', redMid: '#FECACA',
    amber: '#D97706', amberLight: '#FFFBEB',
    text: '#0F172A', textMid: '#475569', textMuted: '#94A3B8', pill: '#F1F5F9',
    border: '#E2E8F0', surface: '#FFFFFF', bg: '#F8FAFC', surfaceHover: '#F1F5F9'
}

type Strategy = {
    strategy_id: string
    name: string
    asset_type: string
    symbols?: string[]
    index?: string
    timeframe: string
    entry_conditions: any[]
    exit_conditions: any
    created_at: string
    creation_prices?: Record<string, number>
}

type LiveStatus = {
    status: string
    broker: string
}

function Card({ children, style = {} }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return (
        <div style={{
            background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`,
            boxShadow: '0 1px 3px rgba(0,0,0,0.04)', padding: 20, ...style,
        }}>{children}</div>
    )
}

function StatusPill({ status }: { status: string }) {
    const map: Record<string, { label: string; bg: string; fg: string }> = {
        ACTIVE: { label: '● LIVE', bg: T.greenLight, fg: T.green },
        PAPER: { label: '◎ PAPER', bg: T.blueLight, fg: T.blue },
        PAUSED: { label: '⏸ PAUSED', bg: T.amberLight, fg: T.amber },
        STOPPED: { label: '■ STOPPED', bg: T.redLight, fg: T.red },
        INACTIVE: { label: '○ INACTIVE', bg: T.pill, fg: T.textMuted },
    }
    const s = map[status] || map.INACTIVE
    return (
        <span style={{
            background: s.bg, color: s.fg, borderRadius: 20, padding: '2px 9px',
            fontSize: 11, fontWeight: 700, letterSpacing: '0.5px', fontFamily: "'DM Mono', monospace",
        }}>{s.label}</span>
    )
}

function StrategiesContent() {
    const router = useRouter()
    const [strategies, setStrategies] = useState<Strategy[]>([])
    const [loading, setLoading] = useState(true)
    const [runningBacktestId, setRunningBacktestId] = useState<string | null>(null)

    const fetchStrategies = async () => {
        try {
            const token = localStorage.getItem(config.authTokenKey)
            const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {}

            const res = await fetch(`${config.apiBaseUrl}/api/strategy`, { headers })
            if (res.status === 401) {
                router.push('/login')
                return
            }
            if (res.ok) {
                const data = await res.json()
                setStrategies(data || [])
            }
        } catch (error) {
            console.error('Failed to fetch strategies:', error)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchStrategies()
    }, [])

    const handleRunBacktest = async (strategyId: string) => {
        setRunningBacktestId(strategyId)
        try {
            // 1. Fetch the complete strategy object
            const { strategy } = await loadStrategy(strategyId)
            // 2. Trigger the backtest API
            const result = await backtestStrategy(strategy, 'quick')
            // 3. Redirect to the results page
            router.push(`/backtest/${result.backtest_id}`)
        } catch (err: any) {
            alert(`Error running backtest: ${err.message || 'Unknown error'}`)
            setRunningBacktestId(null)
        }
    }

    const handleDelete = async (strategyId: string, name: string) => {
        if (!confirm(`Are you sure you want to permanently delete the strategy "${name}"?`)) {
            return
        }

        try {
            const token = localStorage.getItem(config.authTokenKey)
            const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {}
            const res = await fetch(`${config.apiBaseUrl}/api/strategy/${strategyId}`, {
                method: 'DELETE',
                headers
            })

            if (res.ok) {
                setStrategies(prev => prev.filter(s => s.strategy_id !== strategyId))
            } else {
                const err = await res.json()
                alert(`Error deleting strategy: ${err.detail || 'Unknown error'}`)
            }
        } catch (error) {
            console.error('Delete failed:', error)
            alert('Error deleting strategy. Check connection.')
        }
    }

    return (
        <AppShell title="All Strategies" onRefresh={fetchStrategies} showBack={true}>
            <div style={{ padding: '24px', fontFamily: "'DM Sans', sans-serif" }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                    <div>
                        <h1 style={{ fontSize: 24, fontWeight: 800, color: T.navy, margin: 0, letterSpacing: '-0.5px' }}>Your Strategies</h1>
                        <p style={{ fontSize: 13, color: T.textMuted, margin: '4px 0 0' }}>Manage all your built strategies.</p>
                    </div>
                    <Link href="/strategy/new" style={{
                        background: T.blue, color: '#fff', border: 'none', borderRadius: 8,
                        padding: '9px 16px', fontSize: 13, fontWeight: 700, textDecoration: 'none',
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                    }}>
                        <span style={{ fontSize: 16 }}>⚡</span> Create Strategy
                    </Link>
                </div>

                <Card style={{ padding: 0, overflow: 'hidden' }}>
                    {loading ? (
                        <div style={{ padding: 40, textAlign: 'center', color: T.textMuted }}>Loading strategies...</div>
                    ) : strategies.length === 0 ? (
                        <div style={{ padding: '60px 20px', textAlign: 'center' }}>
                            <div style={{ fontSize: 40, marginBottom: 16 }}>📁</div>
                            <h3 style={{ fontSize: 18, color: T.navy, margin: '0 0 8px' }}>No Strategies Found</h3>
                            <p style={{ color: T.textMuted, margin: '0 0 20px' }}>You haven't built any strategies yet.</p>
                            <Link href="/strategy/new" style={{ color: T.blue, fontWeight: 600, textDecoration: 'none' }}>Building your first strategy →</Link>
                        </div>
                    ) : (
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead style={{ background: T.bg, borderBottom: `1px solid ${T.border}` }}>
                                    <tr>
                                        {['Name', 'Asset', 'Config', 'Created', 'Actions'].map(h => (
                                            <th key={h} style={{ padding: '14px 20px', fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.8px', textAlign: 'left' }}>{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {strategies.map((s: Strategy) => {
                                        let displaySymbol = s.asset_type === 'EQUITY' 
                                            ? (s.symbols && s.symbols.length > 0 ? s.symbols.join(', ') : 'No Symbol')
                                            : s.index

                                        if (displaySymbol && displaySymbol.length > 20) {
                                            displaySymbol = displaySymbol.substring(0, 20) + '...'
                                        }

                                        const dateLabel = s.created_at ? new Date(s.created_at).toLocaleDateString() : 'N/A'
                                        const isRunning = runningBacktestId === s.strategy_id

                                        return (
                                            <tr key={s.strategy_id} style={{ borderBottom: `1px solid ${T.border}`, transition: 'background 0.2s' }}
                                                onMouseEnter={e => (e.currentTarget.style.background = T.surfaceHover)}
                                                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                                            >
                                                <td style={{ padding: '16px 20px' }}>
                                                    <div style={{ fontSize: 14, fontWeight: 700, color: T.navy }}>{s.name}</div>
                                                    <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4, fontFamily: "'DM Mono', monospace" }}>ID: {s.strategy_id}</div>
                                                </td>
                                                <td style={{ padding: '16px 20px' }}>
                                                    <div style={{ fontSize: 11, fontWeight: 700, color: T.blue, background: T.blueLight, padding: '2px 6px', borderRadius: 4, display: 'inline-block', marginBottom: 4 }}>{s.asset_type}</div>
                                                    <div style={{ fontSize: 12, fontWeight: 600, color: T.textMid, fontFamily: "'DM Mono', monospace" }}>{displaySymbol}</div>
                                                    {s.creation_prices && Object.keys(s.creation_prices).length > 0 && (
                                                        <div style={{ fontSize: 10, color: T.textMuted, marginTop: 4 }}>
                                                            {Object.keys(s.creation_prices).length === 1 
                                                                ? `Built at: ₹${Object.values(s.creation_prices)[0]}`
                                                                : `Prices captured for ${Object.keys(s.creation_prices).length} stocks`
                                                            }
                                                        </div>
                                                    )}
                                                </td>
                                                <td style={{ padding: '16px 20px' }}>
                                                    <div style={{ fontSize: 12, color: T.text }}>TF: <b>{s.timeframe}</b></div>
                                                    <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>
                                                        {s.entry_conditions?.length || 0} Indicators · Tgt: {s.exit_conditions?.target_pct || '-'}%
                                                    </div>
                                                </td>
                                                <td style={{ padding: '16px 20px', fontSize: 13, color: T.textMid }}>
                                                    {dateLabel}
                                                </td>
                                                <td style={{ padding: '16px 20px' }}>
                                                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                                                        <button 
                                                            onClick={() => handleRunBacktest(s.strategy_id)}
                                                            disabled={runningBacktestId !== null}
                                                            style={{ 
                                                                padding: '6px 12px', border: `1px solid ${T.greenMid}`, borderRadius: 6, 
                                                                background: T.greenLight, fontSize: 12, fontWeight: 700, 
                                                                cursor: runningBacktestId ? 'not-allowed' : 'pointer', color: T.green,
                                                                opacity: runningBacktestId !== null && !isRunning ? 0.5 : 1,
                                                                display: 'flex', alignItems: 'center', gap: 4
                                                            }}
                                                            title="Run Quick Backtest"
                                                        >
                                                            {isRunning ? '⏳ Running...' : '↩ Backtest'}
                                                        </button>
                                                        <button 
                                                            onClick={() => router.push(`/strategy/new?edit=${s.strategy_id}`)}
                                                            style={{ 
                                                                padding: '6px 12px', border: `1px solid ${T.border}`, borderRadius: 6, 
                                                                background: '#fff', fontSize: 12, fontWeight: 600, 
                                                                cursor: 'pointer', color: T.textMid
                                                            }}
                                                            title="Edit Strategy"
                                                        >
                                                            Edit
                                                        </button>
                                                        <button 
                                                            onClick={() => handleDelete(s.strategy_id, s.name)}
                                                            style={{ 
                                                                padding: '6px', border: 'none', background: 'transparent',
                                                                fontSize: 14, cursor: 'pointer',
                                                                color: T.red
                                                            }}
                                                            title="Delete Strategy"
                                                        >
                                                            🗑️
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </Card>
            </div>
        </AppShell>
    )
}

export default function StrategiesPage() {
    return (
        <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>Loading Strategies...</div>}>
            <StrategiesContent />
        </Suspense>
    )
}
