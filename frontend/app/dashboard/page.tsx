'use client'

import { useState, useEffect, useRef, Suspense } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { config } from '@/lib/config'
import { useQuotes } from '@/hooks/useQuotes'
import { StocksView } from '@/components/dashboard/StocksView'
import { IndicesView } from '@/components/dashboard/IndicesView'
import { AppShell } from '@/components/AppShell'
import './dashboard-responsive.css'

// ── Colour tokens ─────────────────────────────────────────────────────────────
const T = {
    bg: '#F8FAFC', surface: '#FFFFFF', surfaceHover: '#F1F5F9',
    border: '#E2E8F0', borderStrong: '#CBD5E1',
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF', blueMid: '#BFDBFE',
    green: '#059669', greenLight: '#ECFDF5', greenMid: '#A7F3D0',
    red: '#DC2626', redLight: '#FEF2F2', redMid: '#FECACA',
    amber: '#D97706', amberLight: '#FFFBEB',
    teal: '#0D9488', tealLight: '#F0FDFA',
    text: '#0F172A', textMid: '#475569', textMuted: '#94A3B8', pill: '#F1F5F9',
}

// ── Types ─────────────────────────────────────────────────────────────────────
interface Strategy {
    id: number
    strategy_id?: string
    name: string
    segment?: string
    asset_type?: string
    status: string
    instrument?: string
    symbol?: string
    symbols?: string[] | string
    pnl: number
    pnlPct: number
    orders: number
    lastSignal: string
    nextCheck: string
    broker: string
    lots: number
}

interface Backtest {
    id: number
    name: string
    period: string
    ret: number
    dd: number
    win: number
    trades: number
    date: string
}

// ── Sub-components ────────────────────────────────────────────────────────────
function Card({ children, style = {} }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return (
        <div style={{
            background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`,
            boxShadow: '0 1px 3px rgba(0,0,0,0.04)', padding: 20, ...style,
        }}>{children}</div>
    )
}

function SectionHeader({ title, action, actionLabel }: { title: string; action?: () => void; actionLabel?: string }) {
    return (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: T.textMid, letterSpacing: '0.6px', textTransform: 'uppercase' }}>{title}</span>
            {action && <button onClick={action} style={{ background: 'none', border: 'none', color: T.blue, fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>{actionLabel} →</button>}
        </div>
    )
}

function PnlBadge({ val, pct, size = 'sm' }: { val: number; pct: string | number; size?: 'sm' | 'md' | 'lg' }) {
    const pos = val >= 0
    const fs = size === 'lg' ? 22 : size === 'md' ? 15 : 13
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            background: pos ? T.greenLight : T.redLight,
            color: pos ? T.green : T.red,
            borderRadius: 6, padding: size === 'lg' ? '6px 12px' : '3px 8px',
            fontWeight: 600, fontSize: fs, fontFamily: "'DM Mono', monospace", letterSpacing: '-0.3px',
        }}>
            {pos ? '▲' : '▼'} {pos ? '' : '-'}Rs. {Math.abs(val).toLocaleString()}
            <span style={{ opacity: 0.7, fontSize: fs - 2 }}>({pos ? '+' : ''}{pct}%)</span>
        </span>
    )
}

function StatusPill({ status }: { status: string }) {
    const map: Record<string, { label: string; bg: string; fg: string }> = {
        live: { label: '● LIVE', bg: T.greenLight, fg: T.green },
        paper: { label: '◎ PAPER', bg: T.blueLight, fg: T.blue },
        paused: { label: '⏸ PAUSED', bg: T.amberLight, fg: T.amber },
        stopped: { label: '■ STOPPED', bg: T.redLight, fg: T.red },
    }
    const s = map[status] || map.stopped
    return (
        <span style={{
            background: s.bg, color: s.fg, borderRadius: 20, padding: '2px 9px',
            fontSize: 11, fontWeight: 700, letterSpacing: '0.5px', fontFamily: "'DM Mono', monospace",
        }}>{s.label}</span>
    )
}

function LiveDot() {
    const [on, setOn] = useState(true)
    useEffect(() => { const t = setInterval(() => setOn(p => !p), 900); return () => clearInterval(t) }, [])
    return <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', background: T.green, opacity: on ? 1 : 0.2, transition: 'opacity 0.3s', marginRight: 5 }} />
}

function Counter({ target, color = T.text }: { target: number; color?: string }) {
    const [val, setVal] = useState(0)
    useEffect(() => {
        const step = target / 40; let cur = 0
        const t = setInterval(() => { cur = Math.min(cur + step, target); setVal(Math.round(cur)); if (cur >= target) clearInterval(t) }, 18)
        return () => clearInterval(t)
    }, [target])
    return <span style={{ color }}>{val.toLocaleString()}</span>
}

function MarketBanner() {
    const [isMounted, setIsMounted] = useState(false)
    const [timeStr, setTimeStr] = useState('')
    const [open, setOpen] = useState(false)

    useEffect(() => {
        setIsMounted(true)
        const updateTime = () => {
            const now = new Date()
            setTimeStr(now.toLocaleTimeString('en-IN', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                timeZone: 'Asia/Kolkata',
                hour12: true
            }))
            const h = now.getHours(), m = now.getMinutes()
            setOpen((h > 9 || (h === 9 && m >= 15)) && (h < 15 || (h === 15 && m <= 30)))
        }
        updateTime()
        const t = setInterval(updateTime, 1000)
        return () => clearInterval(t)
    }, [])

    if (!isMounted) return <div style={{ height: 32 }} /> // Placeholder during SSR to match hydration

    return (
        <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: open ? T.greenLight : T.amberLight,
            border: `1px solid ${open ? T.greenMid : T.amberLight}`,
            borderRadius: 8, padding: '7px 14px', fontSize: 12, fontWeight: 600,
            color: open ? T.green : T.amber, fontFamily: "'DM Mono', monospace",
        }}>
            {open ? <><LiveDot />NSE MARKET OPEN · Closes 15:30 IST</> : <>⏰ NSE MARKET CLOSED · Opens 09:15 IST</>}
            <span style={{ marginLeft: 'auto', fontWeight: 400, opacity: 0.7 }}>
                {timeStr || '--:--'} IST
            </span>
        </div>
    )
}

function DashboardContent() {
    const router = useRouter()
    const [strategies, setStrategies] = useState<Strategy[]>([])
    const [backtests, setBacktests] = useState<Backtest[]>([])
    const [loading, setLoading] = useState(true)
    const { quotes, connected, isLive, marketOpen, lastUpdate } = useQuotes()
    const searchParams = useSearchParams()
    const currentSegment = searchParams.get('segment') || 'Options'
    const [userName, setUserName] = useState('User')
    const [optionsView, setOptionsView] = useState<'overview' | 'indices'>('overview')

    // Fetch user info and data on mount
    useEffect(() => {
        const userStr = localStorage.getItem(config.authUserKey)
        if (userStr) {
            try {
                const user = JSON.parse(userStr)
                setUserName(user.full_name || user.email.split('@')[0])
            } catch { }
        }

        fetchDashboardData()
    }, [])

    const fetchDashboardData = async () => {
        try {
            const token = localStorage.getItem(config.authTokenKey)
            const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {}

            // Fetch strategies
            const strategiesRes = await fetch(`${config.apiBaseUrl}/api/strategy`, { headers })
            if (strategiesRes.ok) {
                const data = await strategiesRes.json()
                setStrategies(Array.isArray(data) ? data : (data.strategies || []))
            } else if (strategiesRes.status === 401) {
                router.push('/login')
                return
            }

            // Fetch recent backtests
            const backtestsRes = await fetch(`${config.apiBaseUrl}/api/backtest`, { headers })
            if (backtestsRes.ok) {
                const data = await backtestsRes.json()
                setBacktests(Array.isArray(data) ? data : (data.backtests || []))
            }
        } catch (error) {
            console.error('Failed to fetch dashboard data:', error)
        } finally {
            setLoading(false)
        }
    }

    const [today, setToday] = useState('')

    useEffect(() => {
        setToday(new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short', year: 'numeric' }))
    }, [])

    return (
        <AppShell title="Dashboard" onRefresh={async () => {
            await fetchDashboardData()
        }}>
            <div className="dashboard-content" style={{
                padding: 24,
                fontFamily: "'DM Sans', sans-serif",
            }}>
                {/* Top bar - hidden on mobile */}
                <div className="desktop-only top-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
                    <div>
                        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: T.navy, letterSpacing: '-0.5px' }}>
                            Hello, {userName} 👋
                        </h1>
                        <p style={{ margin: '4px 0 0', fontSize: 13, color: T.textMuted }}>
                            {today ? `${today} · ` : ''}{currentSegment} Segment
                            <span style={{
                                marginLeft: 8,
                                color: T.blue,
                                fontWeight: 600,
                            }}>
                                {connected ? `· Updates: ${lastUpdate}` : '· Connecting...'}
                            </span>
                        </p>
                    </div>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                        {currentSegment === 'Options' && (
                            <div style={{ display: 'flex', background: T.pill, borderRadius: 8, padding: 3, marginRight: 8 }}>
                                <button
                                    onClick={() => setOptionsView('overview')}
                                    style={{
                                        padding: '6px 12px', fontSize: 12, fontWeight: 700, borderRadius: 6, border: 'none',
                                        background: optionsView === 'overview' ? '#fff' : 'transparent',
                                        color: optionsView === 'overview' ? T.blue : T.textMid,
                                        boxShadow: optionsView === 'overview' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                                        cursor: 'pointer', transition: 'all 0.2s'
                                    }}
                                >Overview</button>
                                <button
                                    onClick={() => setOptionsView('indices')}
                                    style={{
                                        padding: '6px 12px', fontSize: 12, fontWeight: 700, borderRadius: 6, border: 'none',
                                        background: optionsView === 'indices' ? '#fff' : 'transparent',
                                        color: optionsView === 'indices' ? T.blue : T.textMid,
                                        boxShadow: optionsView === 'indices' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                                        cursor: 'pointer', transition: 'all 0.2s'
                                    }}
                                >Indices Explorer</button>
                            </div>
                        )}
                        <MarketBanner />
                        <Link href="/strategy/new" style={{
                            background: T.blue, color: '#fff', border: 'none', borderRadius: 8,
                            padding: '9px 16px', fontSize: 13, fontWeight: 700, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: 6, textDecoration: 'none',
                        }}>
                            <span style={{ fontSize: 16 }}>⚡</span> New Strategy
                        </Link>
                    </div>
                </div>

                {/* Main Content Area */}
                {currentSegment === 'Stocks' ? (
                    <StocksView />
                ) : optionsView === 'indices' ? (
                    <IndicesView />
                ) : (
                    <>
                        {/* Index strip — live from WebSocket */}
                        <div className="index-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 20 }}>
                            {Object.entries(quotes).map(([sym, q]) => (
                                <Card key={sym} style={{ padding: '12px 16px' }}>
                                    <div style={{ fontSize: 11, color: T.textMuted, fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 4 }}>
                                        {sym}
                                        <span style={{ marginLeft: 4, opacity: 0.5, fontSize: 9 }}>{connected ? (isLive ? '●' : '◎') : '○'}</span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                                        <span style={{ fontSize: 16, fontWeight: 700, fontFamily: "'DM Mono', monospace", letterSpacing: '-0.5px', color: q.up ? T.green : T.red }}>
                                            {q.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                        </span>
                                        <span style={{ fontSize: 12, fontWeight: 600, color: q.up ? T.green : T.red, fontFamily: "'DM Mono', monospace" }}>
                                            {q.chg >= 0 ? '+' : ''}{q.chg.toFixed(2)}%
                                        </span>
                                    </div>
                                </Card>
                            ))}
                        </div>

                        {/* Summary stats */}
                        <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 20 }}>
                            {[
                                { label: 'Total Strategies', value: strategies.length, sub: `Built in SignalCraft`, color: T.blue },
                                { label: 'Total Backtests', value: backtests.length, sub: 'Performed all time', color: T.navy },
                                { label: 'Win Rate (Last 10)', value: 68, sub: 'Recent performance', pct: true, color: T.green },
                            ].map(stat => (
                                <Card key={stat.label} style={{ padding: '16px 20px' }}>
                                    <div style={{ fontSize: 11, color: T.textMuted, fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 8 }}>{stat.label}</div>
                                    {stat.pct ? (
                                        <div style={{ fontSize: 26, fontWeight: 800, color: stat.color, letterSpacing: '-1px', fontFamily: "'DM Mono', monospace" }}>{stat.value}%</div>
                                    ) : (
                                        <div style={{ fontSize: 26, fontWeight: 800, color: stat.color, letterSpacing: '-1px' }}>
                                            <Counter target={stat.value!} color={stat.color} />
                                        </div>
                                    )}
                                    {stat.sub && <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>{stat.sub}</div>}
                                </Card>
                            ))}
                        </div>

                        {/* Two column layout */}
                        <div className="two-column-layout" style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16 }}>

                            {/* LEFT: strategies */}
                            <Card>
                                <SectionHeader title="Your Strategies" actionLabel="View all" action={() => router.push('/strategy')} />
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                                    {loading ? (
                                        <div style={{ padding: 20, textAlign: 'center', color: T.textMuted, fontSize: 13 }}>Loading strategies...</div>
                                    ) : strategies.length === 0 ? (
                                        <div style={{ padding: 20, textAlign: 'center', color: T.textMuted, fontSize: 13 }}>
                                            No strategies built yet.<br />
                                            <Link href="/strategy/new" style={{ color: T.blue, fontWeight: 600 }}>Create your first strategy</Link>
                                        </div>
                                    ) : (
                                        strategies.slice(0, 5).map(s => {
                                            const segment = s.asset_type || 'Options'
                                            let displaySymbol = s.symbol || ""
                                            if (!displaySymbol && s.symbols) {
                                                try {
                                                    const parsed = typeof s.symbols === 'string' ? JSON.parse(s.symbols) : s.symbols
                                                    displaySymbol = Array.isArray(parsed) ? parsed.join(', ') : parsed
                                                } catch {
                                                    displaySymbol = s.symbols as string
                                                }
                                            }

                                            return (
                                                <div key={s.id || s.strategy_id} style={{
                                                    border: `1px solid ${T.border}`, borderRadius: 10, padding: '14px 16px', cursor: 'pointer',
                                                    background: T.bg,
                                                    transition: 'all 0.15s',
                                                    marginBottom: 10
                                                }}
                                                    onClick={() => router.push(`/strategy/new?edit=${s.strategy_id}`)}
                                                    onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)')}
                                                    onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
                                                >
                                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                                                        <div>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                                                <span style={{ background: T.blueMid, color: T.blue, borderRadius: 4, padding: '1px 7px', fontSize: 10, fontWeight: 700, letterSpacing: '0.8px', textTransform: 'uppercase' }}>{segment}</span>
                                                            </div>
                                                            <div style={{ fontSize: 14, fontWeight: 700, color: T.navy }}>{s.name}</div>
                                                            <div style={{ fontSize: 12, color: T.textMuted, marginTop: 2, fontFamily: "'DM Mono', monospace" }}>{displaySymbol}</div>
                                                        </div>
                                                        <div style={{ textAlign: 'right' }}>
                                                            <div style={{ fontSize: 10, color: T.textMuted, textTransform: 'uppercase' }}>Built on</div>
                                                            <div style={{ fontSize: 12, fontWeight: 600, color: T.navy }}>{s.lastSignal || 'Recent'}</div>
                                                        </div>
                                                    </div>
                                                </div>
                                            )
                                        })
                                    )}
                                </div>
                            </Card>

                            {/* RIGHT column */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

                                {/* Quick actions */}
                                <Card style={{ padding: 16 }}>
                                    <SectionHeader title="Quick Actions" />
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                        {[
                                            { label: '⚡  Build New Options Strategy', href: '/strategy/new', color: T.blue, bg: T.blueLight },
                                            { label: '📁  Browse All Built Strategies', href: '/strategy', color: T.navy, bg: T.pill },
                                            { label: '↩  Run Backtest on Saved Strategy', href: '/backtest', color: T.textMid, bg: T.surfaceHover },
                                            { label: '⚙  Configure Global Settings', href: '/settings', color: T.amber, bg: T.amberLight },
                                        ].map(a => (
                                            <Link key={a.label} href={a.href} style={{
                                                width: '100%', padding: '10px 14px', border: `1px solid ${T.border}`,
                                                borderRadius: 8, background: a.bg, color: a.color, fontSize: 12, fontWeight: 600,
                                                cursor: 'pointer', textAlign: 'left', textDecoration: 'none', display: 'block',
                                                transition: 'all 0.15s',
                                            }}
                                                onMouseEnter={e => (e.currentTarget.style.opacity = '0.8')}
                                                onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
                                            >{a.label}</Link>
                                        ))}
                                    </div>
                                </Card>

                                {/* Recent backtests */}
                                <Card style={{ padding: 16, flex: 1 }}>
                                    <SectionHeader title="Recent Backtests" actionLabel="View all" action={() => router.push('/backtest')} />
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                        {loading ? (
                                            <div style={{ padding: 20, textAlign: 'center', color: T.textMuted, fontSize: 13 }}>Loading backtests...</div>
                                        ) : backtests.length === 0 ? (
                                            <div style={{ padding: 20, textAlign: 'center', color: T.textMuted, fontSize: 13 }}>
                                                No backtests yet.<br />
                                                <Link href="/strategy/new" style={{ color: T.blue, fontWeight: 600 }}>Create a strategy</Link> to get started.
                                            </div>
                                        ) : (
                                            backtests.map((bt) => (
                                                <div key={bt.id} style={{
                                                    padding: '11px 13px', border: `1px solid ${T.border}`, borderRadius: 8,
                                                    cursor: 'pointer', background: T.bg, transition: 'all 0.15s',
                                                }}
                                                    onMouseEnter={e => (e.currentTarget.style.background = T.surfaceHover)}
                                                    onMouseLeave={e => (e.currentTarget.style.background = T.bg)}
                                                >
                                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                                                        <div style={{ fontSize: 12, fontWeight: 700, color: T.navy, lineHeight: 1.3, flex: 1, marginRight: 8 }}>{bt.name}</div>
                                                        <span style={{ fontSize: 13, fontWeight: 700, color: bt.ret >= 0 ? T.green : T.red, fontFamily: "'DM Mono', monospace", flexShrink: 0 }}>
                                                            {bt.ret >= 0 ? '+' : ''}{bt.ret}%
                                                        </span>
                                                    </div>
                                                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                                                        <span style={{ fontSize: 10, color: T.textMuted, fontFamily: "'DM Mono', monospace" }}>
                                                            {bt.period} · {bt.trades} trades · {bt.win}% win
                                                        </span>
                                                        <span style={{ marginLeft: 'auto', fontSize: 10, color: T.textMuted }}>{bt.date}</span>
                                                    </div>
                                                    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                                                        <button style={{ padding: '3px 10px', border: `1px solid ${T.border}`, borderRadius: 5, background: '#fff', fontSize: 10, fontWeight: 600, cursor: 'pointer', color: T.blue }}>▶ Replay Chart</button>
                                                        <button style={{ padding: '3px 10px', border: `1px solid ${T.border}`, borderRadius: 5, background: '#fff', fontSize: 10, fontWeight: 600, cursor: 'pointer', color: T.textMid }}>📁 View Report</button>
                                                    </div>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </Card>
                            </div>
                        </div>
                    </>
                )}

                {/* Disclaimer footer */}
                <div style={{
                    marginTop: 16, padding: '10px 16px', background: T.amberLight,
                    borderRadius: 8, border: '1px solid #FDE68A', fontSize: 12, color: T.amber,
                    display: 'flex', alignItems: 'center', gap: 8,
                }}>
                    <span>⚠</span>
                    <span><strong>Disclaimer:</strong> SignalCraft is a technology tool only. Past backtest performance does not guarantee future results. All trading decisions are your own responsibility.</span>
                </div>
            </div>
        </AppShell>
    )
}

export default function DashboardPage() {
    return (
        <Suspense fallback={<div style={{ padding: 24, color: '#94A3B8' }}>Loading Dashboard...</div>}>
            <DashboardContent />
        </Suspense>
    )
}
