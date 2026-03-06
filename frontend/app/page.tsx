'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useQuotes } from '@/hooks/useQuotes'

// ── Color tokens (Avoiding blue & purple) ───────────────────────────────────
const T = {
    bg: '#0A0A0A',          // Deepest black for background
    surface: '#121212',     // Slightly lighter for cards
    surfaceHover: '#1A1A1A',
    border: 'rgba(255,255,255,0.08)',
    borderStrong: 'rgba(255,255,255,0.15)',

    // Core brand colors: Emerald Green & Gold / Amber
    emerald: '#10B981', emeraldLight: '#A7F3D0', emeraldDark: '#047857',
    amber: '#F59E0B', amberLight: '#FDE68A', amberDark: '#B45309',
    red: '#DC2626',

    text: '#FFFFFF', textMid: '#A3A3A3', textMuted: '#737373',

    navBgTop: 'rgba(10, 10, 10, 0.7)',
    navBgScrolled: 'rgba(10, 10, 10, 0.95)',
}

// ── Components ──────────────────────────────────────────────────────────────

function LiveDot() {
    const [on, setOn] = useState(true)
    useEffect(() => { const t = setInterval(() => setOn(p => !p), 900); return () => clearInterval(t) }, [])
    return <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: T.emerald, opacity: on ? 1 : 0.2, transition: 'opacity 0.3s', marginRight: 8, boxShadow: `0 0 8px ${T.emerald}` }} />
}

export default function ZenalysLandingPage() {
    const { quotes, connected, isLive, marketOpen } = useQuotes()
    const [scrolled, setScrolled] = useState(false)

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 20)
        window.addEventListener('scroll', handleScroll)
        return () => window.removeEventListener('scroll', handleScroll)
    }, [])

    return (
        <div style={{ minHeight: '100vh', background: T.bg, color: T.text, fontFamily: "'Inter', 'DM Sans', sans-serif", overflowX: 'hidden' }}>

            {/* Background effects */}
            <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: `radial-gradient(circle at 20% 30%, rgba(16, 185, 129, 0.05) 0%, transparent 50%), radial-gradient(circle at 80% 70%, rgba(245, 158, 11, 0.03) 0%, transparent 50%)`, zIndex: 0, pointerEvents: 'none' }} />

            {/* Navigation */}
            <nav style={{
                position: 'fixed', top: 0, width: '100%', height: 72, zIndex: 50,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 5%',
                background: scrolled ? T.navBgScrolled : T.navBgTop,
                backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
                borderBottom: `1px solid ${scrolled ? T.borderStrong : T.border}`,
                transition: 'all 0.3s ease'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 40 }}>
                    {/* Logo Area */}
                    <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.5px', color: '#fff', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ width: 28, height: 28, background: `linear-gradient(135deg, ${T.emerald}, ${T.emeraldDark})`, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, color: '#000', fontSize: 16 }}>Z</div>
                        Zenalys
                    </div>
                    {/* Links */}
                    <div style={{ display: 'flex', gap: 32, fontSize: 14, fontWeight: 500 }}>
                        <a href="#products" style={{ color: T.textMid, textDecoration: 'none', transition: 'color 0.2s' }} onMouseOver={e => e.currentTarget.style.color = '#fff'} onMouseOut={e => e.currentTarget.style.color = T.textMid}>Products</a>
                        <a href="#features" style={{ color: T.textMid, textDecoration: 'none', transition: 'color 0.2s' }} onMouseOver={e => e.currentTarget.style.color = '#fff'} onMouseOut={e => e.currentTarget.style.color = T.textMid}>Features</a>
                        <a href="#infrastructure" style={{ color: T.textMid, textDecoration: 'none', transition: 'color 0.2s' }} onMouseOver={e => e.currentTarget.style.color = '#fff'} onMouseOut={e => e.currentTarget.style.color = T.textMid}>Infrastructure</a>
                    </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <Link href="/login" style={{ padding: '10px 24px', color: '#fff', fontSize: 14, fontWeight: 600, textDecoration: 'none', transition: 'opacity 0.2s' }} onMouseOver={e => e.currentTarget.style.opacity = '0.8'} onMouseOut={e => e.currentTarget.style.opacity = '1'}>
                        Sign In
                    </Link>
                    <Link href="/login?signup=1" style={{ padding: '10px 24px', background: '#fff', color: '#000', borderRadius: 50, fontSize: 14, fontWeight: 700, textDecoration: 'none', transition: 'transform 0.2s', boxShadow: '0 4px 14px rgba(255,255,255,0.1)' }} onMouseOver={e => e.currentTarget.style.transform = 'translateY(-2px)'} onMouseOut={e => e.currentTarget.style.transform = 'translateY(0)'}>
                        Enter SignalCraft
                    </Link>
                </div>
            </nav>

            {/* Live ticker strip (Fixed directly under Nav) */}
            <div style={{
                position: 'fixed', top: 72, width: '100%', zIndex: 40,
                background: 'rgba(0,0,0,0.8)', borderBottom: `1px solid ${T.border}`, padding: '8px 5%',
                backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)'
            }}>
                <div style={{ display: 'flex', gap: 40, alignItems: 'center', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                    <div style={{ display: 'flex', alignItems: 'center', fontSize: 11, color: T.textMid, letterSpacing: '1px', fontWeight: 600 }}>
                        <LiveDot />
                        {connected ? (isLive ? 'LIVE DATA' : 'SIMULATION') : 'DELAYED / OFFLINE'}
                    </div>
                    {Object.entries(quotes).slice(0, 5).map(([sym, q]) => (
                        <div key={sym} style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                            <span style={{ fontSize: 12, color: T.textMid, fontWeight: 700 }}>{sym}</span>
                            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, fontWeight: 700, color: '#fff' }}>
                                {q.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, fontWeight: 600, color: q.up ? T.emerald : T.red }}>
                                {q.up ? '+' : ''}{q.chg.toFixed(2)}%
                            </span>
                        </div>
                    ))}
                    <div style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 700, letterSpacing: '1px' }}>
                        <span style={{ color: marketOpen ? T.emerald : T.amber }}>
                            {marketOpen ? '● NSE OPEN' : '⏰ MARKET CLOSED'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Main Content wrapper */}
            <div style={{ position: 'relative', zIndex: 10, paddingTop: 160 }}>

                {/* Hero Section */}
                <section style={{ padding: '60px 5% 100px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(16, 185, 129, 0.1)', border: `1px solid rgba(16, 185, 129, 0.2)`, color: T.emeraldLight, borderRadius: 50, padding: '6px 16px', fontSize: 13, fontWeight: 600, marginBottom: 32, letterSpacing: '0.5px' }}>
                        <span style={{ display: 'inline-block', width: 6, height: 6, background: T.emerald, borderRadius: '50%' }}></span>
                        Next-Gen Algorithmic Trading Infrastructure
                    </div>

                    <h1 style={{ fontWeight: 800, fontSize: '4.5rem', lineHeight: 1.05, marginBottom: 24, letterSpacing: '-0.03em', maxWidth: 900 }}>
                        Institutional Grade Tools for <br />
                        <span style={{ background: `linear-gradient(to right, ${T.emerald}, #FFFFFF)`, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Independent Traders</span>
                    </h1>

                    <p style={{ fontSize: '1.25rem', color: T.textMid, lineHeight: 1.6, marginBottom: 48, maxWidth: 680 }}>
                        Zenalys builds uncompromising automated trading platforms. Backtest flawlessly, execute in milliseconds, and scale your alpha without writing a single line of complex integration code.
                    </p>

                    <div style={{ display: 'flex', gap: 16, justifyContent: 'center' }}>
                        <Link href="/login" style={{ padding: '16px 36px', background: '#fff', color: '#000', borderRadius: 50, fontSize: 16, fontWeight: 700, textDecoration: 'none', transition: 'all 0.3s', boxShadow: '0 8px 25px rgba(255,255,255,0.15)' }} onMouseOver={e => e.currentTarget.style.transform = 'translateY(-2px)'} onMouseOut={e => e.currentTarget.style.transform = 'translateY(0)'}>
                            Explore SignalCraft
                        </Link>
                        <a href="#infrastructure" style={{ padding: '16px 36px', background: 'transparent', border: `2px solid ${T.borderStrong}`, color: '#fff', borderRadius: 50, fontSize: 16, fontWeight: 700, textDecoration: 'none', transition: 'all 0.3s' }} onMouseOver={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.borderColor = '#fff'; e.currentTarget.style.transform = 'translateY(-2px)' }} onMouseOut={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = T.borderStrong; e.currentTarget.style.transform = 'translateY(0)' }}>
                            View Infrastructure
                        </a>
                    </div>
                </section>

                {/* Stats / Proof Section */}
                <section style={{ padding: '0 5% 100px', display: 'flex', justifyContent: 'center' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 40, width: '100%', maxWidth: 1000, padding: '40px 0', borderTop: `1px solid ${T.border}`, borderBottom: `1px solid ${T.border}` }}>
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#fff', marginBottom: 4 }}>&lt;10ms</div>
                            <div style={{ color: T.textMuted, fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>Execution Latency</div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#fff', marginBottom: 4 }}>99.9%</div>
                            <div style={{ color: T.textMuted, fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>API Uptime</div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#fff', marginBottom: 4 }}>4</div>
                            <div style={{ color: T.textMuted, fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>Native Brokers</div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#fff', marginBottom: 4 }}>Live</div>
                            <div style={{ color: T.textMuted, fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>Tick By Tick Data</div>
                        </div>
                    </div>
                </section>

                {/* Product Spotlight: SignalCraft */}
                <section id="products" style={{ padding: '40px 5% 100px' }}>
                    <div style={{ maxWidth: 1200, margin: '0 auto', background: T.surface, border: `1px solid ${T.border}`, borderRadius: 24, padding: 60, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 60, alignItems: 'center', position: 'relative', overflow: 'hidden' }}>
                        {/* Glow effect */}
                        <div style={{ position: 'absolute', top: -100, right: -100, width: 400, height: 400, background: T.emerald, filter: 'blur(150px)', opacity: 0.1, borderRadius: '50%' }} />

                        <div>
                            <div style={{ fontSize: 14, fontWeight: 700, color: T.emerald, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 16 }}>Flagship Product</div>
                            <h2 style={{ fontSize: '3rem', fontWeight: 800, marginBottom: 24, letterSpacing: '-0.02em' }}>Signal<span style={{ color: T.emerald }}>Craft</span></h2>
                            <p style={{ fontSize: '1.1rem', color: T.textMid, lineHeight: 1.7, marginBottom: 32 }}>
                                Our premier visual platform designed for all types of traders. Build complex, multi-leg strategies without writing code. Backtest against years of historical data instantly, and push to live execution with one click.
                            </p>
                            <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 40px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                                {[
                                    'Visual No-Code Strategy Builder',
                                    'TradingView-style interactive chart replay',
                                    'Nifty, BankNifty, & FinNifty Options Support',
                                    'Direct execution via Dhan, Zerodha, Shoonya'
                                ].map((item, i) => (
                                    <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, color: '#fff', fontSize: '1rem', fontWeight: 500 }}>
                                        <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', color: T.emerald, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>✓</div>
                                        {item}
                                    </li>
                                ))}
                            </ul>
                            <Link href="/login?signup=1" style={{ display: 'inline-block', padding: '14px 32px', background: T.emerald, color: '#000', borderRadius: 8, fontSize: 15, fontWeight: 700, textDecoration: 'none', transition: 'all 0.2s', boxShadow: '0 4px 14px rgba(16, 185, 129, 0.3)' }} onMouseOver={e => e.currentTarget.style.transform = 'translateY(-2px)'} onMouseOut={e => e.currentTarget.style.transform = 'translateY(0)'}>
                                Open SignalCraft App →
                            </Link>
                        </div>

                        {/* Mockup / Abstract visual */}
                        <div style={{ background: '#000', border: `1px solid ${T.borderStrong}`, borderRadius: 16, height: 400, display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 20px 40px rgba(0,0,0,0.5)' }}>
                            <div style={{ height: 40, borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', padding: '0 16px', gap: 8 }}>
                                <div style={{ width: 10, height: 10, borderRadius: '50%', background: T.borderStrong }} />
                                <div style={{ width: 10, height: 10, borderRadius: '50%', background: T.borderStrong }} />
                                <div style={{ width: 10, height: 10, borderRadius: '50%', background: T.borderStrong }} />
                            </div>
                            <div style={{ flex: 1, padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderBottom: `1px dashed ${T.borderStrong}`, paddingBottom: 16, height: '40%' }}>
                                    {[40, 70, 45, 90, 60, 80, 50, 100].map((h, i) => (
                                        <div key={i} style={{ width: '8%', height: `${h}%`, background: i === 7 ? T.emerald : T.borderStrong, borderRadius: '4px 4px 0 0', opacity: i === 7 ? 1 : 0.5 }} />
                                    ))}
                                </div>
                                <div style={{ display: 'flex', gap: 16 }}>
                                    <div style={{ flex: 1, height: 80, background: 'rgba(16, 185, 129, 0.05)', border: `1px solid rgba(16, 185, 129, 0.2)`, borderRadius: 8, padding: 12 }}>
                                        <div style={{ width: '40%', height: 12, background: 'rgba(16, 185, 129, 0.4)', borderRadius: 4, marginBottom: 8 }} />
                                        <div style={{ width: '80%', height: 8, background: T.borderStrong, borderRadius: 4 }} />
                                    </div>
                                    <div style={{ flex: 1, height: 80, background: T.border, borderRadius: 8, padding: 12, opacity: 0.5 }}>
                                        <div style={{ width: '40%', height: 12, background: T.borderStrong, borderRadius: 4, marginBottom: 8 }} />
                                        <div style={{ width: '60%', height: 8, background: T.borderStrong, borderRadius: 4 }} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Features / Infrastructure */}
                <section id="infrastructure" style={{ padding: '60px 5% 100px' }}>
                    <div style={{ textAlign: 'center', marginBottom: 60 }}>
                        <h2 style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: 16 }}>Built for Performance</h2>
                        <p style={{ fontSize: '1.2rem', color: T.textMid }}>The infrastructure you need to deploy edge-seeking algorithms.</p>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 24, maxWidth: 1200, margin: '0 auto' }}>
                        {[
                            { icon: '⚡', title: 'Low Latency Execution', desc: 'Direct REST/WebSocket API connections to brokers bypass intermediaries, saving critical milliseconds on order execution.' },
                            { icon: '🔒', title: 'Encrypted Credential Vault', desc: 'Your API keys, secrets, and TOTP pins are encrypted and securely stored at the user-level in our PostgreSQL database.' },
                            { icon: '🔄', title: 'Resilient Order Management', desc: 'Automated state reconciliation and retry logic ensures your positions are accurate even during broker API hiccups.' },
                            { icon: '📊', title: 'High-Fidelity Data', desc: 'Tick-level data processing and accurate OHLCV candle generation feed into your technical indicators precisely.' },
                            { icon: '🛡️', title: 'Risk Guardrails', desc: 'Built-in max drawdown limits, position sizing constraints, and automated kill-switches protect your capital.' },
                            { icon: '🔌', title: 'Multi-Broker Accounts', desc: 'Run strategies across multiple accounts or different brokers simultaneously from a single unified dashboard.' }
                        ].map(f => (
                            <div key={f.title} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 16, padding: 32, transition: 'all 0.3s' }} onMouseOver={e => { e.currentTarget.style.transform = 'translateY(-5px)'; e.currentTarget.style.borderColor = T.borderStrong; e.currentTarget.style.background = T.surfaceHover }} onMouseOut={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.borderColor = T.border; e.currentTarget.style.background = T.surface }}>
                                <div style={{ width: 56, height: 56, background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.borderStrong}`, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, marginBottom: 24 }}>
                                    {f.icon}
                                </div>
                                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: 12, color: '#fff' }}>{f.title}</h3>
                                <p style={{ color: T.textMuted, lineHeight: 1.6, fontSize: '0.95rem' }}>{f.desc}</p>
                            </div>
                        ))}
                    </div>
                </section>

                {/* Footer CTA */}
                <section style={{ padding: '80px 5% 100px', textAlign: 'center', background: `linear-gradient(to bottom, transparent, rgba(16, 185, 129, 0.05))` }}>
                    <h2 style={{ fontSize: '3rem', fontWeight: 800, marginBottom: 24 }}>Ready to trade programmatically?</h2>
                    <p style={{ fontSize: '1.2rem', color: T.textMid, marginBottom: 40, maxWidth: 600, margin: '0 auto 40px' }}>
                        Join the beta of SignalCraft today. Connect your broker and deploy your first algorithmic strategy in minutes.
                    </p>
                    <Link href="/login?signup=1" style={{ display: 'inline-block', padding: '16px 40px', background: '#fff', color: '#000', borderRadius: 50, fontSize: 16, fontWeight: 800, textDecoration: 'none', transition: 'all 0.2s', boxShadow: '0 8px 30px rgba(255,255,255,0.1)' }} onMouseOver={e => e.currentTarget.style.transform = 'scale(1.05)'} onMouseOut={e => e.currentTarget.style.transform = 'scale(1)'}>
                        Start Deploying
                    </Link>
                </section>

                {/* Footer */}
                <footer style={{ borderTop: `1px solid ${T.border}`, padding: '40px 5%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.9rem', color: T.textMuted }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, color: '#fff' }}>
                        <div style={{ width: 20, height: 20, background: T.emerald, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#000', fontSize: 12 }}>Z</div>
                        Zenalys
                    </div>
                    <div>
                        Technology platform only. Zenalys is not a registered investment advisor. Past performance does not guarantee future results.
                    </div>
                    <div>
                        © {new Date().getFullYear()} Zenalys. All rights reserved.
                    </div>
                </footer>
            </div>
        </div>
    )
}
