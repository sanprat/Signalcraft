'use client'

import { useEffect, useState, useRef } from 'react'
import Link from 'next/link'
import { useQuotes } from '@/hooks/useQuotes'

const MOBILE_BREAKPOINT = 768

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
    const ref = useRef<HTMLSpanElement>(null)
    useEffect(() => {
        const el = ref.current
        if (!el) return
        let t: ReturnType<typeof setInterval> | null = null
        const start = () => { if (!t) t = setInterval(() => setOn(p => !p), 900) }
        const stop = () => { if (t) { clearInterval(t); t = null } }
        const obs = new IntersectionObserver(([entry]) => { entry.isIntersecting ? start() : stop() })
        obs.observe(el)
        return () => { stop(); obs.disconnect() }
    }, [])
    return <span ref={ref} style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: T.emerald, opacity: on ? 1 : 0.2, transition: 'opacity 0.3s', marginRight: 8, boxShadow: `0 0 8px ${T.emerald}` }} />
}

// Mobile Menu Component
function MobileMenu({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
    if (!isOpen) return null

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.95)',
            zIndex: 100,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 32,
        }} onClick={onClose}>
            <a href="#products" style={{ color: '#fff', fontSize: 24, fontWeight: 700, textDecoration: 'none' }}>Products</a>
            <a href="#features" style={{ color: '#fff', fontSize: 24, fontWeight: 700, textDecoration: 'none' }}>Features</a>
            <a href="#how-it-works" style={{ color: '#fff', fontSize: 24, fontWeight: 700, textDecoration: 'none' }}>How It Works</a>
            <Link href="/pricing" style={{ color: '#fff', fontSize: 24, fontWeight: 700, textDecoration: 'none' }}>Pricing</Link>
            <Link href="/login" style={{ color: '#fff', fontSize: 24, fontWeight: 700, textDecoration: 'none' }}>Sign In</Link>
                            <Link href="/pricing" style={{
                                padding: '14px 32px',
                                background: T.emerald,
                                color: '#000',
                                borderRadius: 50,
                                fontSize: 18,
                                fontWeight: 700,
                                textDecoration: 'none',
                            }}>Subscribe</Link>
            <button onClick={onClose} style={{
                position: 'absolute',
                top: 20,
                right: 20,
                background: 'transparent',
                border: 'none',
                color: '#fff',
                fontSize: 32,
                cursor: 'pointer',
            }}>×</button>
        </div>
    )
}

export default function ZenalysLandingPage() {
    const { quotes, connected, isLive, marketOpen, lastUpdate } = useQuotes()
    const [scrolled, setScrolled] = useState(false)
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
    const [isMobile, setIsMobile] = useState(false)

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 20)
        window.addEventListener('scroll', handleScroll)
        
        const checkMobile = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
        checkMobile()
        window.addEventListener('resize', checkMobile)
        
        return () => {
            window.removeEventListener('scroll', handleScroll)
            window.removeEventListener('resize', checkMobile)
        }
    }, [])

    return (
        <div style={{ minHeight: '100vh', background: T.bg, color: T.text, fontFamily: "'Inter', 'DM Sans', sans-serif", overflowX: 'hidden' }}>

            {/* Background effects */}
            <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: `radial-gradient(circle at 20% 30%, rgba(16, 185, 129, 0.05) 0%, transparent 50%), radial-gradient(circle at 80% 70%, rgba(245, 158, 11, 0.03) 0%, transparent 50%)`, zIndex: 0, pointerEvents: 'none' }} />

            {/* Mobile Menu Overlay */}
            <MobileMenu isOpen={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} />

            {/* Navigation */}
            <nav style={{
                position: 'fixed', top: 0, width: '100%', height: isMobile ? 64 : 72, zIndex: 50,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: isMobile ? '0 16px' : '0 5%',
                background: scrolled ? T.navBgScrolled : T.navBgTop,
                backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
                borderBottom: `1px solid ${scrolled ? T.borderStrong : T.border}`,
                transition: 'all 0.3s ease'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 12 : 40 }}>
                    {/* Logo Area */}
                    <Link href="/" style={{ fontSize: isMobile ? 20 : 24, fontWeight: 800, letterSpacing: '-0.5px', color: '#fff', display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
                        <div style={{ 
                            width: isMobile ? 24 : 28, 
                            height: isMobile ? 24 : 28, 
                            background: `linear-gradient(135deg, ${T.emerald}, ${T.emeraldDark})`, 
                            borderRadius: 6, 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center', 
                            fontWeight: 900, 
                            color: '#000', 
                            fontSize: isMobile ? 14 : 16 
                        }}>Z</div>
                        Zenalys
                    </Link>
                    
                    {/* Desktop Links */}
                    {!isMobile && (
                        <div style={{ display: 'flex', gap: 32, fontSize: 14, fontWeight: 500 }}>
                            <a href="#products" style={{ color: T.textMid, textDecoration: 'none', transition: 'color 0.2s' }} onMouseOver={e => e.currentTarget.style.color = '#fff'} onMouseOut={e => e.currentTarget.style.color = T.textMid}>Products</a>
                            <a href="#features" style={{ color: T.textMid, textDecoration: 'none', transition: 'color 0.2s' }} onMouseOver={e => e.currentTarget.style.color = '#fff'} onMouseOut={e => e.currentTarget.style.color = T.textMid}>Features</a>
                            <a href="#how-it-works" style={{ color: T.textMid, textDecoration: 'none', transition: 'color 0.2s' }} onMouseOver={e => e.currentTarget.style.color = '#fff'} onMouseOut={e => e.currentTarget.style.color = T.textMid}>How It Works</a>
                            <Link href="/pricing" style={{ color: T.textMid, textDecoration: 'none', transition: 'color 0.2s' }} onMouseOver={e => e.currentTarget.style.color = '#fff'} onMouseOut={e => e.currentTarget.style.color = T.textMid}>Pricing</Link>
                        </div>
                    )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 12 : 16 }}>
                    {!isMobile ? (
                        <>
                            <Link href="/login" style={{ padding: '10px 24px', color: '#fff', fontSize: 14, fontWeight: 600, textDecoration: 'none', transition: 'opacity 0.2s' }} onMouseOver={e => e.currentTarget.style.opacity = '0.8'} onMouseOut={e => e.currentTarget.style.opacity = '1'}>
                                Sign In
                            </Link>
                            <Link href="/pricing" style={{ padding: '10px 24px', background: '#fff', color: '#000', borderRadius: 50, fontSize: 14, fontWeight: 700, textDecoration: 'none', transition: 'transform 0.2s', boxShadow: '0 4px 14px rgba(255,255,255,0.1)' }} onMouseOver={e => e.currentTarget.style.transform = 'translateY(-2px)'} onMouseOut={e => e.currentTarget.style.transform = 'translateY(0)'}>
                                Register here
                            </Link>
                        </>
                    ) : (
                        <button 
                            onClick={() => setMobileMenuOpen(true)}
                            style={{
                                background: 'transparent',
                                border: `1px solid ${T.borderStrong}`,
                                color: '#fff',
                                padding: '8px 12px',
                                borderRadius: 8,
                                cursor: 'pointer',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 4,
                            }}
                        >
                            <span style={{ display: 'block', width: 20, height: 2, background: '#fff' }} />
                            <span style={{ display: 'block', width: 20, height: 2, background: '#fff' }} />
                            <span style={{ display: 'block', width: 20, height: 2, background: '#fff' }} />
                        </button>
                    )}
                </div>
            </nav>

            {/* Live ticker strip (Fixed directly under Nav) */}
            <div style={{
                position: 'fixed', top: isMobile ? 64 : 72, width: '100%', zIndex: 40,
                background: 'rgba(0,0,0,0.8)', borderBottom: `1px solid ${T.border}`,
                padding: isMobile ? '6px 16px' : '8px 5%',
                backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
                overflow: 'hidden'
            }}>
                <div className="ticker-scroll" style={{ display: 'flex', gap: isMobile ? 20 : 40, alignItems: 'center', overflowX: 'auto', whiteSpace: 'nowrap', scrollbarWidth: 'none', msOverflowStyle: 'none', WebkitOverflowScrolling: 'touch' } as React.CSSProperties}>
                    <div style={{ display: 'flex', alignItems: 'center', fontSize: isMobile ? 10 : 11, color: T.textMid, letterSpacing: '1px', fontWeight: 600, flexShrink: 0 }}>
                        <LiveDot />
                        {connected ? (isLive ? 'LIVE DATA' : 'SIMULATION') : 'DELAYED / OFFLINE'}
                    </div>
                    {(Object.entries(quotes ?? {})).slice(0, isMobile ? 3 : 5).map(([sym, q]) => (
                        <div key={sym} style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexShrink: 0 }}>
                            <span style={{ fontSize: isMobile ? 11 : 12, color: T.textMid, fontWeight: 700 }}>{sym}</span>
                            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: isMobile ? 12 : 13, fontWeight: 700, color: '#fff' }}>
                                {q.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: isMobile ? 11 : 12, fontWeight: 600, color: q.up ? T.emerald : T.red }}>
                                {q.up ? '+' : ''}{q.chg.toFixed(2)}%
                            </span>
                        </div>
                    ))}
                    <div style={{ marginLeft: 'auto', fontSize: isMobile ? 10 : 11, fontWeight: 700, letterSpacing: '1px', flexShrink: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
                        {lastUpdate && (
                            <span style={{ color: T.textMuted, fontWeight: 500, letterSpacing: 0 }}>
                                {new Date(lastUpdate).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                            </span>
                        )}
                        <span style={{ color: marketOpen ? T.emerald : T.amber }}>
                            {marketOpen ? '● NSE OPEN' : '○ MARKET CLOSED'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Main Content wrapper */}
            <div style={{ position: 'relative', zIndex: 10, paddingTop: 120 }}>

                {/* Hero Section */}
                <section style={{ 
                    padding: isMobile ? '40px 16px 60px' : '60px 5% 100px', 
                    display: 'flex', 
                    flexDirection: 'column', 
                    alignItems: 'center', 
                    textAlign: 'center' 
                }}>
                    <div style={{ 
                        display: 'inline-flex', 
                        alignItems: 'center', 
                        gap: 8, 
                        background: 'rgba(16, 185, 129, 0.1)', 
                        border: `1px solid rgba(16, 185, 129, 0.2)`, 
                        color: T.emeraldLight, 
                        borderRadius: 50, 
                        padding: isMobile ? '4px 12px' : '6px 16px', 
                        fontSize: isMobile ? 11 : 13, 
                        fontWeight: 600, 
                        marginBottom: isMobile ? 20 : 32, 
                        letterSpacing: '0.5px',
                        whiteSpace: 'nowrap'
                    }}>
                        <span style={{ display: 'inline-block', width: 6, height: 6, background: T.emerald, borderRadius: '50%' }}></span>
                        Next-Gen Strategy Research
                    </div>

                    <h1 style={{ 
                        fontWeight: 800, 
                        fontSize: isMobile ? '2rem' : '4.5rem', 
                        lineHeight: 1.1, 
                        marginBottom: isMobile ? 16 : 24, 
                        letterSpacing: '-0.03em',
                        maxWidth: isMobile ? '100%' : 900 
                    }}>
                        Build. Backtest. Alert.<br />
                        <span style={{ background: `linear-gradient(to right, ${T.emerald}, #FFFFFF)`, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Trade smarter.</span>
                    </h1>

                    <p style={{ 
                        fontSize: isMobile ? '1rem' : '1.25rem', 
                        color: T.textMid, 
                        lineHeight: 1.6, 
                        marginBottom: isMobile ? 32 : 48, 
                        maxWidth: isMobile ? '100%' : 680,
                        padding: isMobile ? '0 8px' : 0
                    }}>
                        Design trading strategies visually, validate them against years of historical data, and get notified when your conditions trigger. No code required.
                    </p>

                    <div style={{ 
                        display: 'flex', 
                        gap: isMobile ? 12 : 16, 
                        justifyContent: 'center',
                        flexDirection: isMobile ? 'column' : 'row',
                        width: isMobile ? '100%' : 'auto'
                    }}>
                        <Link href="/pricing" style={{ 
                            padding: isMobile ? '14px 28px' : '16px 36px', 
                            background: '#fff', 
                            color: '#000', 
                            borderRadius: 50, 
                            fontSize: isMobile ? 15 : 16, 
                            fontWeight: 700, 
                            textDecoration: 'none', 
                            transition: 'all 0.3s', 
                            boxShadow: '0 8px 25px rgba(255,255,255,0.15)',
                            textAlign: 'center',
                        }} onMouseOver={e => e.currentTarget.style.transform = 'translateY(-2px)'} onMouseOut={e => e.currentTarget.style.transform = 'translateY(0)'}>
                            View Pricing
                        </Link>
                        <a href="#how-it-works" style={{ 
                            padding: isMobile ? '14px 28px' : '16px 36px', 
                            background: 'transparent', 
                            border: `2px solid ${T.borderStrong}`, 
                            color: '#fff', 
                            borderRadius: 50, 
                            fontSize: isMobile ? 15 : 16, 
                            fontWeight: 700, 
                            textDecoration: 'none', 
                            transition: 'all 0.3s',
                            textAlign: 'center',
                        }} onMouseOver={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.borderColor = '#fff'; e.currentTarget.style.transform = 'translateY(-2px)' }} onMouseOut={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = T.borderStrong; e.currentTarget.style.transform = 'translateY(0)' }}>
                            See How It Works
                        </a>
                    </div>
                </section>

                {/* Stats / Proof Section */}
                <section style={{ 
                    padding: isMobile ? '0 16px 60px' : '0 5% 100px', 
                    display: 'flex', 
                    justifyContent: 'center' 
                }}>
                    <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: isMobile ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)', 
                        gap: isMobile ? 24 : 40, 
                        width: '100%', 
                        maxWidth: 1000, 
                        padding: isMobile ? '24px 16px' : '40px 0', 
                        borderTop: `1px solid ${T.border}`, 
                        borderBottom: `1px solid ${T.border}` 
                    }}>
                        {[
                            { value: '16', label: 'Built-in Indicators' },
                            { value: 'Sub-second', label: 'Backtest Engine' },
                            { value: '12', label: 'Stock Screeners' },
                            { value: 'Multi-Symbol', label: 'Strategy Support' }
                        ].map((stat, i) => (
                            <div key={i} style={{ textAlign: 'center' }}>
                                <div style={{ fontSize: isMobile ? '1.75rem' : '2.5rem', fontWeight: 800, color: '#fff', marginBottom: 4 }}>{stat.value}</div>
                                <div style={{ color: T.textMuted, fontSize: isMobile ? '0.8rem' : '0.9rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>{stat.label}</div>
                            </div>
                        ))}
                    </div>
                </section>

                {/* Product Spotlight: SignalCraft */}
                <section id="products" style={{ padding: isMobile ? '40px 16px' : '40px 5% 100px' }}>
                    <div style={{ 
                        maxWidth: 1200, 
                        margin: '0 auto', 
                        background: T.surface, 
                        border: `1px solid ${T.border}`, 
                        borderRadius: 24, 
                        padding: isMobile ? 24 : 60, 
                        display: 'grid', 
                        gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', 
                        gap: isMobile ? 32 : 60, 
                        alignItems: 'center', 
                        position: 'relative', 
                        overflow: 'hidden' 
                    }}>
                        {/* Glow effect */}
                        <div style={{ position: 'absolute', top: -100, right: -100, width: 400, height: 400, background: T.emerald, filter: 'blur(150px)', opacity: 0.1, borderRadius: '50%' }} />

                        <div>
                            <div style={{ fontSize: isMobile ? 12 : 14, fontWeight: 700, color: T.emerald, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 16 }}>Flagship Product</div>
                            <h2 style={{ fontSize: isMobile ? '2rem' : '3rem', fontWeight: 800, marginBottom: isMobile ? 16 : 24, letterSpacing: '-0.02em' }}>Signal<span style={{ color: T.emerald }}>Craft</span></h2>
                            <p style={{ fontSize: isMobile ? '1rem' : '1.1rem', color: T.textMid, lineHeight: 1.7, marginBottom: isMobile ? 24 : 32 }}>
                                Our visual platform for building and validating trading strategies. Design entry and exit conditions with drag-and-drop, backtest against years of historical data, and receive alerts when your conditions trigger.
                            </p>
                            <ul style={{ listStyle: 'none', padding: 0, margin: `0 0 ${isMobile ? 24 : 40}px`, display: 'flex', flexDirection: 'column', gap: isMobile ? 12 : 16 }}>
                                {[
                                    'Visual No-Code Strategy Builder',
                                    'TradingView-style interactive chart replay',
                                    'Nifty, BankNifty, & FinNifty Options Support',
                                    'Condition-Based Alert Notifications'
                                ].map((item, i) => (
                                    <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, color: '#fff', fontSize: isMobile ? '0.9rem' : '1rem', fontWeight: 500 }}>
                                        <div style={{ width: isMobile ? 20 : 24, height: isMobile ? 20 : 24, borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', color: T.emerald, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: isMobile ? 10 : 12 }}>✓</div>
                                        {item}
                                    </li>
                                ))}
                            </ul>
                                <Link href="/pricing" style={{ 
                                    display: 'inline-block', 
                                    padding: isMobile ? '12px 24px' : '14px 32px', 
                                    background: T.emerald, 
                                    color: '#000', 
                                    borderRadius: 8, 
                                    fontSize: isMobile ? 14 : 15, 
                                    fontWeight: 700, 
                                    textDecoration: 'none', 
                                    transition: 'all 0.2s', 
                                    boxShadow: '0 4px 14px rgba(16, 185, 129, 0.3)',
                                    width: isMobile ? '100%' : 'auto',
                                    textAlign: 'center',
                                    boxSizing: 'border-box',
                                }} onMouseOver={e => e.currentTarget.style.transform = 'translateY(-2px)'} onMouseOut={e => e.currentTarget.style.transform = 'translateY(0)'}>
                                    Subscribe →
                                </Link>
                        </div>

                        {/* Mockup / Abstract visual */}
                        <div style={{ 
                            background: '#000', 
                            border: `1px solid ${T.borderStrong}`, 
                            borderRadius: 16, 
                            height: isMobile ? 280 : 400, 
                            display: 'flex', 
                            flexDirection: 'column', 
                            overflow: 'hidden', 
                            boxShadow: '0 20px 40px rgba(0,0,0,0.5)' 
                        }}>
                            <div style={{ height: isMobile ? 32 : 40, borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', padding: isMobile ? '0 12px' : '0 16px', gap: 8 }}>
                                <div style={{ width: isMobile ? 8 : 10, height: isMobile ? 8 : 10, borderRadius: '50%', background: T.borderStrong }} />
                                <div style={{ width: isMobile ? 8 : 10, height: isMobile ? 8 : 10, borderRadius: '50%', background: T.borderStrong }} />
                                <div style={{ width: isMobile ? 8 : 10, height: isMobile ? 8 : 10, borderRadius: '50%', background: T.borderStrong }} />
                            </div>
                            <div style={{ flex: 1, padding: isMobile ? 16 : 24, display: 'flex', flexDirection: 'column', gap: isMobile ? 12 : 16 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderBottom: `1px dashed ${T.borderStrong}`, paddingBottom: isMobile ? 12 : 16, height: '40%' }}>
                                    {[40, 70, 45, 90, 60, 80, 50, 100].map((h, i) => (
                                        <div key={i} style={{ width: '8%', height: `${h}%`, background: i === 7 ? T.emerald : T.borderStrong, borderRadius: '4px 4px 0 0', opacity: i === 7 ? 1 : 0.5 }} />
                                    ))}
                                </div>
                                <div style={{ display: 'flex', gap: isMobile ? 12 : 16 }}>
                                    <div style={{ flex: 1, height: isMobile ? 60 : 80, background: 'rgba(16, 185, 129, 0.05)', border: `1px solid rgba(16, 185, 129, 0.2)`, borderRadius: isMobile ? 6 : 8, padding: isMobile ? 8 : 12 }}>
                                        <div style={{ width: '40%', height: isMobile ? 10 : 12, background: 'rgba(16, 185, 129, 0.4)', borderRadius: 4, marginBottom: isMobile ? 6 : 8 }} />
                                        <div style={{ width: '80%', height: isMobile ? 6 : 8, background: T.borderStrong, borderRadius: 4 }} />
                                    </div>
                                    <div style={{ flex: 1, height: isMobile ? 60 : 80, background: T.border, borderRadius: isMobile ? 6 : 8, padding: isMobile ? 8 : 12, opacity: 0.5 }}>
                                        <div style={{ width: '40%', height: isMobile ? 10 : 12, background: T.borderStrong, borderRadius: 4, marginBottom: isMobile ? 6 : 8 }} />
                                        <div style={{ width: '60%', height: isMobile ? 6 : 8, background: T.borderStrong, borderRadius: 4 }} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Features / Infrastructure */}
                <section id="how-it-works" style={{ padding: isMobile ? '40px 16px 60px' : '60px 5% 100px' }}>
                    <div style={{ textAlign: 'center', marginBottom: isMobile ? 40 : 60 }}>
                        <h2 style={{ fontSize: isMobile ? '1.75rem' : '2.5rem', fontWeight: 800, marginBottom: isMobile ? 12 : 16 }}>Built for Research</h2>
                        <p style={{ fontSize: isMobile ? '1rem' : '1.2rem', color: T.textMid, padding: isMobile ? '0 8px' : 0 }}>Everything you need to build, validate, and monitor trading strategies.</p>
                    </div>

                    <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(300px, 1fr))', 
                        gap: isMobile ? 16 : 24, 
                        maxWidth: 1200, 
                        margin: '0 auto' 
                    }}>
                        {[
                            { icon: '🧩', title: 'Visual Strategy Builder', desc: 'Drag-and-drop entry and exit conditions with 16 indicators, 8 operators, and ALL/ANY logic. Build complex strategies without writing code.' },
                            { icon: '📊', title: 'Multi-Indicator Engine', desc: 'RSI, SMA, EMA, MACD, Supertrend, Bollinger Bands, ATR, ADX, and more. Stack and combine indicators with configurable parameters.' },
                            { icon: '📈', title: 'Historical Replay & Charting', desc: 'Interactive candlestick charts with trade annotations. Replay your strategy decisions on years of NIFTY500 and FnO data.' },
                            { icon: '🧪', title: 'Backtest Analytics', desc: 'Detailed PnL reports with win rate, max drawdown, equity curves, per-symbol breakdowns, and full trade logs.' },
                            { icon: '🔔', title: 'Condition-Based Alerts', desc: 'Set up alerts when indicators cross thresholds, price hits levels, or custom conditions trigger. Get notified via Telegram instantly.' },
                            { icon: '🔍', title: 'Stock Screeners', desc: '12 built-in screeners — Minervini, VCP, IBD CAN SLIM, RSI Momentum, MACD Crossover, and more. Filter NIFTY500 in seconds.' }
                        ].map(f => (
                            <div key={f.title} style={{ 
                                background: T.surface, 
                                border: `1px solid ${T.border}`, 
                                borderRadius: 16, 
                                padding: isMobile ? 24 : 32, 
                                transition: 'all 0.3s' 
                            }} onMouseOver={e => { 
                                e.currentTarget.style.transform = isMobile ? 'none' : 'translateY(-5px)'; 
                                e.currentTarget.style.borderColor = T.borderStrong; 
                                e.currentTarget.style.background = T.surfaceHover 
                            }} onMouseOut={e => { 
                                e.currentTarget.style.transform = 'translateY(0)'; 
                                e.currentTarget.style.borderColor = T.border; 
                                e.currentTarget.style.background = T.surface 
                            }}>
                                <div style={{ 
                                    width: isMobile ? 48 : 56, 
                                    height: isMobile ? 48 : 56, 
                                    background: 'rgba(255,255,255,0.05)', 
                                    border: `1px solid ${T.borderStrong}`, 
                                    borderRadius: isMobile ? 10 : 12, 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    justifyContent: 'center', 
                                    fontSize: isMobile ? 20 : 24, 
                                    marginBottom: isMobile ? 16 : 24 
                                }}>
                                    {f.icon}
                                </div>
                                <h3 style={{ fontSize: isMobile ? '1.1rem' : '1.25rem', fontWeight: 700, marginBottom: isMobile ? 8 : 12, color: '#fff' }}>{f.title}</h3>
                                <p style={{ color: T.textMuted, lineHeight: 1.6, fontSize: isMobile ? '0.9rem' : '0.95rem' }}>{f.desc}</p>
                            </div>
                        ))}
                    </div>
                </section>

                {/* Footer CTA */}
                <section style={{ 
                    padding: isMobile ? '60px 16px 80px' : '80px 5% 100px', 
                    textAlign: 'center', 
                    background: `linear-gradient(to bottom, transparent, rgba(16, 185, 129, 0.05))` 
                }}>
                    <h2 style={{ fontSize: isMobile ? '1.75rem' : '3rem', fontWeight: 800, marginBottom: isMobile ? 16 : 24, padding: isMobile ? '0 8px' : 0 }}>Ready to validate your edge?</h2>
                    <p style={{ 
                        fontSize: isMobile ? '1rem' : '1.2rem',
                        color: T.textMid,
                        marginBottom: isMobile ? 32 : 40,
                        maxWidth: 600,
                        margin: `0 auto ${isMobile ? 32 : 40}px`,
                        padding: isMobile ? '0 8px' : 0
                    }}>
                        Build strategies, backtest against historical data, and get alerts when your conditions trigger with one monthly subscription.
                    </p>
                    <Link href="/pricing" style={{ 
                        display: 'inline-block', 
                        padding: isMobile ? '14px 32px' : '16px 40px', 
                        background: '#fff', 
                        color: '#000', 
                        borderRadius: 50, 
                        fontSize: isMobile ? 15 : 16, 
                        fontWeight: 800, 
                        textDecoration: 'none', 
                        transition: 'all 0.2s', 
                        boxShadow: '0 8px 30px rgba(255,255,255,0.1)',
                        width: isMobile ? '100%' : 'auto',
                        maxWidth: isMobile ? '280px' : 'none',
                        boxSizing: 'border-box',
                    }} onMouseOver={e => e.currentTarget.style.transform = 'scale(1.05)'} onMouseOut={e => e.currentTarget.style.transform = 'scale(1)'}>
                        Subscribe Now
                    </Link>
                </section>

                {/* Footer */}
                <footer style={{ 
                    borderTop: `1px solid ${T.border}`, 
                    padding: isMobile ? '32px 16px' : '40px 5%', 
                    display: 'flex', 
                    flexDirection: isMobile ? 'column' : 'row',
                    justifyContent: isMobile ? 'center' : 'space-between', 
                    alignItems: 'center', 
                    fontSize: isMobile ? '0.8rem' : '0.9rem', 
                    color: T.textMuted,
                    gap: isMobile ? 16 : 0,
                    textAlign: isMobile ? 'center' : undefined
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, color: '#fff' }}>
                        <div style={{ width: 20, height: 20, background: T.emerald, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#000', fontSize: 12 }}>Z</div>
                        Zenalys
                    </div>
                    <div style={{ maxWidth: isMobile ? '100%' : 600 }}>
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
