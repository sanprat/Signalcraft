'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { config } from '@/lib/config'

const T = {
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF',
    border: '#E2E8F0', textMuted: '#94A3B8', textMid: '#475569', text: '#0F172A',
    red: '#DC2626', redLight: '#FEF2F2', green: '#059669', greenLight: '#ECFDF5',
}

const PLAN_CODE = 'zenalys-monthly-799'

export default function RegisterPage() {
    const [selectedPlan, setSelectedPlan] = useState(PLAN_CODE)
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [fullName, setFullName] = useState('')
    const [error, setError] = useState('')
    const [success, setSuccess] = useState('')
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        const params = new URLSearchParams(window.location.search)
        setSelectedPlan(params.get('plan') || PLAN_CODE)
    }, [])

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setSuccess('')
        setLoading(true)
        try {
            const res = await fetch(`${config.apiBaseUrl}/api/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email,
                    password,
                    full_name: fullName,
                    plan_code: selectedPlan,
                }),
            })
            const data = await res.json()
            if (!res.ok) { setError(data.detail || 'Registration failed'); return }
            setSuccess(data.message || 'Account created. Complete subscription payment before signing in.')
        } catch {
            setError('Backend not reachable. Make sure the API is running.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div style={{
            minHeight: '100vh', display: 'flex', flexDirection: 'column',
            background: '#F8FAFC', fontFamily: "'DM Sans', sans-serif",
        }}>
            <nav style={{ background: T.navy, padding: '0 48px', height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Link href="/" style={{ fontSize: 18, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px', textDecoration: 'none' }}>
                    Zenalys
                </Link>
                <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
                    <Link href="/pricing" style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)', textDecoration: 'none' }}>Pricing</Link>
                    <Link href="/login" style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', textDecoration: 'none' }}>← Back to login</Link>
                </div>
            </nav>

            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
                <div style={{ width: '100%', maxWidth: 440 }}>
                    <div style={{ background: '#fff', borderRadius: 16, border: `1px solid ${T.border}`, boxShadow: '0 4px 24px rgba(0,0,0,0.06)', padding: 40 }}>

                        <div style={{ textAlign: 'center', marginBottom: 32 }}>
                            <div style={{ fontSize: 22, fontWeight: 800, color: T.navy, marginBottom: 6 }}>Subscribe to Zenalys</div>
                            <div style={{ fontSize: 13, color: T.textMuted }}>Create your account against the monthly plan to request access</div>
                        </div>

                        <div style={{ marginBottom: 20, borderRadius: 12, border: `1px solid ${T.border}`, background: T.blueLight, padding: '16px 18px' }}>
                            <div style={{ fontSize: 12, fontWeight: 700, color: T.textMid, textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 8 }}>
                                Selected Plan
                            </div>
                            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
                                <div>
                                    <div style={{ fontSize: 18, fontWeight: 800, color: T.navy }}>Zenalys Monthly</div>
                                    <div style={{ fontSize: 12, color: T.textMuted }}>Plan code: {selectedPlan}</div>
                                </div>
                                <div style={{ fontSize: 18, fontWeight: 800, color: T.navy }}>₹799/mo</div>
                            </div>
                        </div>

                        {error && (
                            <div style={{ background: T.redLight, border: `1px solid #FECACA`, borderRadius: 8, padding: '10px 14px', fontSize: 13, color: T.red, marginBottom: 20 }}>
                                {error}
                            </div>
                        )}

                        {success && (
                            <div style={{ background: T.greenLight, border: `1px solid #A7F3D0`, borderRadius: 8, padding: '10px 14px', fontSize: 13, color: T.green, marginBottom: 20 }}>
                                {success}
                            </div>
                        )}

                        <form onSubmit={handleRegister}>
                            <div style={{ marginBottom: 16 }}>
                                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: T.textMid, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Full Name</label>
                                <input type="text" required value={fullName} onChange={e => setFullName(e.target.value)}
                                    placeholder="Your name"
                                    style={{ width: '100%', padding: '10px 12px', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, outline: 'none', fontFamily: "'DM Sans', sans-serif" }} />
                            </div>
                            <div style={{ marginBottom: 16 }}>
                                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: T.textMid, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Email</label>
                                <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                                    placeholder="you@example.com"
                                    style={{ width: '100%', padding: '10px 12px', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, outline: 'none', fontFamily: "'DM Sans', sans-serif" }} />
                            </div>
                            <div style={{ marginBottom: 24 }}>
                                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: T.textMid, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Password</label>
                                <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    style={{ width: '100%', padding: '10px 12px', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, outline: 'none', fontFamily: "'DM Sans', sans-serif" }} />
                            </div>
                            <button type="submit" disabled={loading} style={{
                                width: '100%', padding: '12px', background: T.blue, color: '#fff',
                                border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: 'pointer',
                                opacity: loading ? 0.7 : 1,
                            }}>
                                {loading ? 'Submitting subscription...' : '⚡ Subscribe & Create Account'}
                            </button>
                        </form>

                        <div style={{ marginTop: 18, padding: '12px 14px', borderRadius: 8, background: '#F8FAFC', border: `1px solid ${T.border}`, fontSize: 12, color: T.textMid, lineHeight: 1.6 }}>
                            New registrations are created in a pending state until subscription payment and activation are completed. Existing active accounts can continue signing in as usual.
                        </div>

                        <div style={{ marginTop: 24, textAlign: 'center', fontSize: 12, color: T.textMuted }}>
                            Already have an account?{' '}
                            <Link href="/login" style={{ color: T.blue, fontWeight: 600 }}>Sign in</Link>
                        </div>
                    </div>

                    <div style={{ marginTop: 20, textAlign: 'center', fontSize: 11, color: T.textMuted, lineHeight: 1.6 }}>
                        {config.appName} is a personal trading tool. All data stays on your machine.
                    </div>
                </div>
            </div>
        </div>
    )
}
