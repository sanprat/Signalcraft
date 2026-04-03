'use client'

import { useState, useEffect, Suspense } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/AppShell'
import { listStrategies, deleteStrategy, loadStrategy, backtestStrategy } from '@/lib/api/strategy'
import type { StrategyListItem } from '@/lib/api/strategy'

const T = {
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF', blueMid: '#BFDBFE',
    green: '#059669', greenLight: '#ECFDF5', greenMid: '#A7F3D0',
    red: '#DC2626', redLight: '#FEF2F2', redMid: '#FECACA',
    amber: '#D97706', amberLight: '#FFFBEB',
    text: '#0F172A', textMid: '#475569', textMuted: '#94A3B8', pill: '#F1F5F9',
    border: '#E2E8F0', surface: '#FFFFFF', bg: '#F8FAFC', surfaceHover: '#F1F5F9'
}

function Card({ children, style = {} }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return (
        <div style={{
            background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`,
            boxShadow: '0 1px 3px rgba(0,0,0,0.04)', padding: 20, ...style,
        }}>{children}</div>
    )
}

function StrategiesContent() {
    const router = useRouter()
    const [strategies, setStrategies] = useState<StrategyListItem[]>([])
    const [loading, setLoading] = useState(true)
    const [processingId, setProcessingId] = useState<string | null>(null)

    const fetchStrategies = async () => {
        try {
            let result = await listStrategies()
            if (result && Array.isArray(result)) {
                setStrategies(result)
            }
        } catch (error: any) {
            console.error('Failed to fetch strategies:', error)
            // Unauthorized – redirect to login
            if (error?.message && (error.message.includes('401') || error.message.includes('Unauthorized'))) {
                router.push('/login')
            }
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchStrategies()
    }, [])

    const handleRunBacktest = async (strategyId: string) => {
        setProcessingId(strategyId)
        try {
            const { strategy } = await loadStrategy(strategyId)
            const result = await backtestStrategy(strategy)
            router.push(`/backtest/${result.backtest_id}`)
        } catch (err: any) {
            alert(`Error running backtest: ${err.message || 'Unknown error'}`)
            setProcessingId(null)
        }
    }

    const handleDelete = async (strategyId: string, name: string) => {
        if (!confirm(`Are you sure you want to permanently delete the strategy "${name}"?`)) {
            return
        }
        try {
            await deleteStrategy(strategyId)
            setStrategies(prev => prev.filter(s => s.id !== strategyId))
        } catch (err: any) {
            alert(`Error deleting strategy: ${err.message || 'Unknown error'}`)
        }
    }

    return (
        <AppShell title="My Saved Strategies" onRefresh={fetchStrategies} showBack={true}>
            <div style={{ padding: '24px', fontFamily: "'DM Sans', sans-serif" }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                    <div>
                        <h1 style={{ fontSize: 24, fontWeight: 800, color: T.navy, margin: 0, letterSpacing: '-0.5px' }}>My Saved Strategies</h1>
                        <p style={{ fontSize: 13, color: T.textMuted, margin: '4px 0 0' }}>
                            {strategies.length} {strategies.length === 1 ? 'strategy saved' : 'strategies saved'}.
                        </p>
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
                            <h3 style={{ fontSize: 18, color: T.navy, margin: '0 0 8px' }}>No Saved Strategies</h3>
                            <p style={{ color: T.textMuted, margin: '0 0 20px' }}>You have no saved strategies yet. Build one using the strategy builder.</p>
                            <Link href="/strategy/new" style={{ color: T.blue, fontWeight: 600, textDecoration: 'none' }}>Create your first strategy →</Link>
                        </div>
                    ) : (
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead style={{ background: T.bg, borderBottom: `1px solid ${T.border}` }}>
                                    <tr>
                                        {['Name', 'Asset', 'Config', 'Updated', 'Actions'].map(h => (
                                            <th key={h} style={{ padding: '14px 20px', fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.8px', textAlign: 'left' }}>{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {strategies.map((s: StrategyListItem) => {
                                        const displaySymbol = s.symbols && s.symbols.length > 0
                                            ? (s.symbols.length > 3 ? s.symbols.slice(0, 3).join(', ') + '…' : s.symbols.join(', '))
                                            : 'N/A'

                                        const dateLabel = (s.updated_at || s.created_at)
                                            ? new Date(s.updated_at || s.created_at).toLocaleDateString()
                                            : 'N/A'
                                        const isProcessing = processingId === s.id

                                        return (
                                            <tr key={s.id} style={{ borderBottom: `1px solid ${T.border}`, transition: 'background 0.2s' }}
                                                onMouseEnter={e => (e.currentTarget.style.background = T.surfaceHover)}
                                                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                                            >
                                                <td style={{ padding: '16px 20px' }}>
                                                    <div style={{ fontSize: 14, fontWeight: 700, color: T.navy }}>{s.name}</div>
                                                    <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4, fontFamily: "'DM Mono', monospace" }}>ID: {s.id}</div>
                                                </td>
                                                <td style={{ padding: '16px 20px' }}>
                                                    <div style={{ fontSize: 11, fontWeight: 700, color: T.blue, background: T.blueLight, padding: '2px 6px', borderRadius: 4, display: 'inline-block', marginBottom: 4 }}>{s.asset_type}</div>
                                                    <div style={{ fontSize: 12, fontWeight: 600, color: T.textMid, fontFamily: "'DM Mono', monospace" }}>{displaySymbol}</div>
                                                </td>
                                                <td style={{ padding: '16px 20px' }}>
                                                    <div style={{ fontSize: 12, color: T.text }}>TF: <b>{s.timeframe}</b></div>
                                                    <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>
                                                        {s.entry_conditions_count || 0} conditions · {s.exit_rules_count || 0} exits
                                                    </div>
                                                </td>
                                                <td style={{ padding: '16px 20px', fontSize: 13, color: T.textMid }}>
                                                    {dateLabel}
                                                </td>
                                                <td style={{ padding: '16px 20px' }}>
                                                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                                                        <button
                                                            onClick={() => handleRunBacktest(s.id)}
                                                            disabled={processingId !== null}
                                                            style={{
                                                                padding: '6px 12px', border: `1px solid ${T.greenMid}`, borderRadius: 6,
                                                                background: T.greenLight, fontSize: 12, fontWeight: 700,
                                                                cursor: processingId ? 'not-allowed' : 'pointer', color: T.green,
                                                                opacity: processingId !== null && !isProcessing ? 0.5 : 1,
                                                                display: 'flex', alignItems: 'center', gap: 4
                                                            }}
                                                            title="Run Quick Backtest"
                                                        >
                                                            {isProcessing ? '⏳ Running...' : '↩ Backtest'}
                                                        </button>
                                                        <button
                                                            onClick={() => router.push(`/strategy/new?edit=${s.id}`)}
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
                                                            onClick={() => handleDelete(s.id, s.name)}
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
