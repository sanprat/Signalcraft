'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useQuotes } from '@/hooks/useQuotes'

const T = {
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF',
    green: '#059669', greenLight: '#ECFDF5', greenMid: '#A7F3D0',
    red: '#DC2626', amber: '#D97706', text: '#0F172A',
    textMid: '#475569', textMuted: '#94A3B8', border: '#E2E8F0', surface: '#FFFFFF',
}

const FEATURES = [
    { icon: '🏗️', title: 'No-Code Strategy Builder', desc: 'Pick indicators, set entry/exit rules — no Python required.' },
    { icon: '📊', title: 'TradingView-Style Replay', desc: 'Replay 2 years of candle data and see every trade on chart.' },
    { icon: '🚀', title: 'Direct Broker Integration', desc: 'One click to go live via Zerodha, Shoonya, Flattrade or Dhan.' },
    { icon: '⚡', title: 'Options + Swing', desc: 'NIFTY / BANKNIFTY / FINNIFTY weekly options. Nifty-500 swing (V2).' },
]

function LiveDot() {
    const [on, setOn] = useState(true)
    useEffect(() => { const t = setInterval(() => setOn(p => !p), 900); return () => clearInterval(t) }, [])
    return <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', background: T.green, opacity: on ? 1 : 0.2, transition: 'opacity 0.3s', marginRight: 6 }} />
}

export default function LandingPage() {
    const { quotes, connected, isLive, marketOpen } = useQuotes()

    return (
        <div style={{ minHeight: '100vh', background: '#F8FAFC', fontFamily: "'DM Sans', sans-serif" }}>

            {/* Nav */}
            <nav style={{ background: T.navy, padding: '0 48px', height: 60, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px' }}>
                    Signal<span style={{ color: '#38BDF8' }}>Craft</span>
                    <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', marginLeft: 8, letterSpacing: '1px', fontWeight: 400, textTransform: 'uppercase' }}>Beta</span>
                </div>
                <div style={{ display: 'flex', gap: 12 }}>
                    <Link href="/login" style={{
                        padding: '8px 20px', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 8,
                        color: '#fff', fontSize: 13, fontWeight: 600, textDecoration: 'none',
                    }}>Login</Link>
                    <Link href="/login?signup=1" style={{
                        padding: '8px 20px', background: '#38BDF8', borderRadius: 8,
                        color: T.navy, fontSize: 13, fontWeight: 700, textDecoration: 'none',
                    }}>Get Started Free</Link>
                </div>
            </nav>

            {/* Live ticker strip */}
            <div style={{ background: T.navy, borderTop: '1px solid rgba(255,255,255,0.06)', padding: '10px 48px' }}>
                <div style={{ display: 'flex', gap: 32, alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', fontSize: 11, color: 'rgba(255,255,255,0.4)', letterSpacing: '0.5px' }}>
                        <LiveDot />
                        {connected ? (isLive ? 'LIVE' : 'SIM') : 'DELAYED'}
                    </div>
                    {Object.entries(quotes).map(([sym, q]) => (
                        <div key={sym} style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontWeight: 600, letterSpacing: '0.5px' }}>{sym}</span>
                            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 14, fontWeight: 700, color: '#fff' }}>
                                {q.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, fontWeight: 600, color: q.up ? '#34D399' : '#F87171' }}>
                                {q.up ? '+' : ''}{q.chg.toFixed(2)}%
                            </span>
                        </div>
                    ))}
                    <div style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 600 }}>
                        <span style={{ color: marketOpen ? '#34D399' : '#FBBF24' }}>
                            {marketOpen ? '● NSE OPEN' : '⏰ MARKET CLOSED'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Hero */}
            <div style={{ maxWidth: 800, margin: '0 auto', padding: '80px 24px 60px', textAlign: 'center' }}>
                <div style={{ display: 'inline-block', background: T.blueLight, color: T.blue, borderRadius: 20, padding: '4px 14px', fontSize: 12, fontWeight: 700, marginBottom: 24, letterSpacing: '0.5px' }}>
                    No Pine Script · No Quantiply · One Platform
                </div>
                <h1 style={{ fontWeight: 800, fontSize: '4rem', lineHeight: 1.1, marginBottom: '20px', letterSpacing: '-0.02em' }}>
                    Build, Backtest & Deploy <br />
                    <span style={{ color: T.blue }}>FnO &amp; Stock trading Strategies</span> in Minutes
                </h1>
                <p style={{ fontSize: 17, color: T.textMid, lineHeight: 1.7, marginBottom: 36, maxWidth: 560, margin: '0 auto 36px' }}>
                    Visual no-code strategy builder. Build, backtest, and execute strategies for <strong>Options</strong> (NIFTY, BANKNIFTY, FINNIFTY) and <strong>Stocks</strong> (Nifty 500) — all in one platform.
                </p>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
                    <Link href="/login" style={{
                        padding: '13px 32px', background: T.blue, borderRadius: 10,
                        color: '#fff', fontSize: 15, fontWeight: 700, textDecoration: 'none',
                        boxShadow: '0 4px 14px rgba(29, 78, 216, 0.35)',
                    }}>⚡ Start Building for Free</Link>
                    <Link href="/login" style={{
                        padding: '13px 28px', border: `1px solid ${T.border}`, borderRadius: 10,
                        color: T.textMid, fontSize: 14, fontWeight: 600, textDecoration: 'none',
                    }}>Login →</Link>
                </div>
            </div>

            {/* Features */}
            <div style={{ maxWidth: 960, margin: '0 auto', padding: '0 24px 80px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
                    {FEATURES.map(f => (
                        <div key={f.title} style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
                            <div style={{ fontSize: 28, marginBottom: 12 }}>{f.icon}</div>
                            <div style={{ fontSize: 14, fontWeight: 700, color: T.navy, marginBottom: 6 }}>{f.title}</div>
                            <div style={{ fontSize: 13, color: T.textMuted, lineHeight: 1.6 }}>{f.desc}</div>
                        </div>
                    ))}
                </div>
            </div>

            {/* CTA banner */}
            <div style={{ background: T.navy, padding: '48px', textAlign: 'center' }}>
                <h2 style={{ fontSize: 28, fontWeight: 800, color: '#fff', marginBottom: 12, letterSpacing: '-0.5px' }}>
                    Ready to craft your signals?
                </h2>
                <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 14, marginBottom: 24 }}>No credit card. No platform fees during beta.</p>
                <Link href="/login?signup=1" style={{
                    padding: '14px 36px', background: '#38BDF8', borderRadius: 10,
                    color: T.navy, fontSize: 14, fontWeight: 700, textDecoration: 'none',
                }}>Get Started Free</Link>
            </div>

            {/* Footer */}
            <div style={{ background: T.navy, borderTop: '1px solid rgba(255,255,255,0.06)', padding: '16px 48px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', fontWeight: 600 }}>
                    Signal<span style={{ color: '#38BDF8' }}>Craft</span> © 2026
                </span>
                <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)' }}>
                    Technology tool only. Not investment advice. Past performance ≠ future results.
                </span>
            </div>
        </div>
    )
}
