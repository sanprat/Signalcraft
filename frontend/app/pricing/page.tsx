'use client'

import Link from 'next/link'

const T = {
    bg: '#0A0A0A',
    surface: '#121212',
    border: 'rgba(255,255,255,0.08)',
    borderStrong: 'rgba(255,255,255,0.16)',
    emerald: '#10B981',
    emeraldDark: '#047857',
    amber: '#F59E0B',
    text: '#FFFFFF',
    textMid: '#A3A3A3',
    textMuted: '#737373',
}

const PLAN_CODE = 'zenalys-monthly-799'

export default function PricingPage() {
    return (
        <div style={{ minHeight: '100vh', background: T.bg, color: T.text, fontFamily: "'DM Sans', sans-serif" }}>
            <nav style={{
                position: 'sticky',
                top: 0,
                zIndex: 50,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '18px 5%',
                background: 'rgba(10, 10, 10, 0.88)',
                backdropFilter: 'blur(12px)',
                borderBottom: `1px solid ${T.border}`,
            }}>
                <Link href="/" style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.5px', color: '#fff', display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
                    <span style={{ width: 28, height: 28, background: `linear-gradient(135deg, ${T.emerald}, ${T.emeraldDark})`, borderRadius: 6, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, color: '#000', fontSize: 16 }}>Z</span>
                    Zenalys
                </Link>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <Link href="/login" style={{ color: '#fff', textDecoration: 'none', fontSize: 14, fontWeight: 600 }}>Sign In</Link>
                    <Link href={`/register?plan=${PLAN_CODE}`} style={{ padding: '10px 20px', background: '#fff', color: '#000', borderRadius: 999, textDecoration: 'none', fontSize: 14, fontWeight: 700 }}>
                        Subscribe
                    </Link>
                </div>
            </nav>

            <main style={{ padding: '72px 5% 96px' }}>
                <div style={{ maxWidth: 980, margin: '0 auto', textAlign: 'center' }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 999, border: `1px solid ${T.borderStrong}`, color: T.amber, background: 'rgba(245, 158, 11, 0.08)', fontSize: 13, fontWeight: 700, marginBottom: 22 }}>
                        Zenalys Pricing
                    </div>
                    <h1 style={{ fontSize: 'clamp(2.5rem, 6vw, 4.6rem)', lineHeight: 1.05, fontWeight: 800, margin: '0 0 16px', letterSpacing: '-0.04em' }}>
                        One plan. Full access.
                    </h1>
                    <p style={{ maxWidth: 680, margin: '0 auto 48px', color: T.textMid, fontSize: 18, lineHeight: 1.7 }}>
                        Build strategies, run backtests, monitor alerts, and access the full SignalCraft workflow with a single monthly subscription.
                    </p>
                </div>

                <div style={{ maxWidth: 1120, margin: '0 auto', display: 'grid', gridTemplateColumns: 'minmax(320px, 420px) minmax(320px, 1fr)', gap: 28, alignItems: 'stretch' }}>
                    <section style={{ background: T.surface, border: `1px solid ${T.borderStrong}`, borderRadius: 28, padding: 34, boxShadow: '0 24px 60px rgba(0,0,0,0.28)' }}>
                        <div style={{ display: 'inline-flex', padding: '6px 12px', borderRadius: 999, background: 'rgba(16, 185, 129, 0.12)', color: T.emerald, fontSize: 12, fontWeight: 800, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 18 }}>
                            Monthly Subscription
                        </div>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
                            <span style={{ fontSize: 54, fontWeight: 800, letterSpacing: '-0.05em' }}>₹799</span>
                            <span style={{ color: T.textMid, fontSize: 18 }}>/ month</span>
                        </div>
                        <p style={{ color: T.textMid, lineHeight: 1.7, fontSize: 15, marginBottom: 26 }}>
                            Best for individual traders who want visual strategy building, backtesting, and alert-driven execution workflows inside one platform.
                        </p>

                        <div style={{ display: 'grid', gap: 12, marginBottom: 28 }}>
                            {[
                                'Visual strategy builder with multi-section rule editing',
                                'Historical backtesting with chart and trade analytics',
                                'Telegram-ready alert workflow support',
                                'Live strategy monitoring and deployment stack',
                                'Ongoing feature updates within the same monthly plan',
                            ].map((item) => (
                                <div key={item} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, color: '#fff', fontSize: 15, lineHeight: 1.5 }}>
                                    <span style={{ width: 22, height: 22, borderRadius: '50%', background: 'rgba(16, 185, 129, 0.14)', color: T.emerald, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800, flexShrink: 0 }}>✓</span>
                                    <span>{item}</span>
                                </div>
                            ))}
                        </div>

                        <Link href={`/register?plan=${PLAN_CODE}`} style={{ display: 'block', width: '100%', textAlign: 'center', padding: '14px 18px', background: '#fff', color: '#000', borderRadius: 14, textDecoration: 'none', fontSize: 16, fontWeight: 800 }}>
                            Continue to Subscribe
                        </Link>
                    </section>

                    <section style={{ background: 'linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02))', border: `1px solid ${T.border}`, borderRadius: 28, padding: 34 }}>
                        <h2 style={{ fontSize: 24, fontWeight: 800, margin: '0 0 18px' }}>How access works</h2>
                        <div style={{ display: 'grid', gap: 18, color: T.textMid, fontSize: 15, lineHeight: 1.7 }}>
                            <div>
                                Pick the monthly plan and create the account you want to use for the subscription.
                            </div>
                            <div>
                                New registrations are marked as pending until payment and activation are completed.
                            </div>
                            <div>
                                Existing pre-created accounts continue to work normally, so you can still share test credentials with selected users.
                            </div>
                        </div>

                        <div style={{ marginTop: 28, padding: 22, borderRadius: 18, background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.18)' }}>
                            <div style={{ color: T.amber, fontWeight: 800, marginBottom: 8 }}>Current release note</div>
                            <div style={{ color: T.textMid, fontSize: 14, lineHeight: 1.7 }}>
                                This release adds the pricing and subscription gate in the app flow. Payment activation can now control sign-in access for newly created accounts.
                            </div>
                        </div>
                    </section>
                </div>
            </main>
        </div>
    )
}
