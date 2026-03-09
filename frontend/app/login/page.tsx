'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { config } from '@/lib/config'

const T = {
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF',
    border: '#E2E8F0', textMuted: '#94A3B8', textMid: '#475569', text: '#0F172A',
    red: '#DC2626', redLight: '#FEF2F2',
}

export default function LoginPage() {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)
    const [showInstall, setShowInstall] = useState(false)
    const [deferredPrompt, setDeferredPrompt] = useState<any>(null)
    const router = useRouter()

    // PWA Install Prompt on Login Page
    useEffect(() => {
        const handleBeforeInstallPrompt = (e: Event) => {
            e.preventDefault()
            console.log('[PWA Login] Install prompt available')
            setDeferredPrompt(e)
            setShowInstall(true)
        }

        const handleAppInstalled = () => {
            console.log('[PWA Login] App installed!')
            setShowInstall(false)
            setDeferredPrompt(null)
        }

        window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
        window.addEventListener('appinstalled', handleAppInstalled)

        return () => {
            window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
            window.removeEventListener('appinstalled', handleAppInstalled)
        }
    }, [])

    const handleInstall = async () => {
        if (!deferredPrompt) return
        try {
            deferredPrompt.prompt()
            const { outcome } = await deferredPrompt.userChoice
            console.log('[PWA Login] User choice:', outcome)
        } catch (error) {
            console.error('[PWA Login] Error:', error)
        } finally {
            setShowInstall(false)
            setDeferredPrompt(null)
        }
    }

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setLoading(true)
        try {
            const formData = new URLSearchParams()
            formData.append('username', email)
            formData.append('password', password)

            const res = await fetch(`${config.apiBaseUrl}/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData,
            })
            const data = await res.json()
            if (!res.ok) { setError(data.detail || 'Login failed'); return }
            localStorage.setItem(config.authTokenKey, data.access_token)
            localStorage.setItem(config.authUserKey, JSON.stringify(data.user))
            document.cookie = `${config.authTokenKey}=${data.access_token}; path=/; max-age=${config.tokenMaxAgeDays * 60 * 60 * 24}`
            router.push('/dashboard')
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
            {/* PWA Install Banner - Shows on Login Page */}
            {showInstall && (
                <div style={{
                    position: 'fixed',
                    top: 'max(20px, env(safe-area-inset-top))',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'linear-gradient(135deg, #10B981, #047857)',
                    color: '#fff',
                    padding: '14px 18px',
                    borderRadius: 14,
                    boxShadow: '0 8px 30px rgba(16, 185, 129, 0.4)',
                    zIndex: 10001,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    maxWidth: '95%',
                    width: 380,
                    animation: 'slideDown 0.4s ease-out',
                }}>
                    <div style={{
                        width: 44,
                        height: 44,
                        background: 'rgba(255,255,255,0.2)',
                        borderRadius: 12,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 22,
                        fontWeight: 900,
                        flexShrink: 0,
                    }}>
                        SC
                    </div>
                    <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 3 }}>
                            📲 Install SignalCraft
                        </div>
                        <div style={{ fontSize: 12, opacity: 0.95, lineHeight: 1.3 }}>
                            Add app to home screen for quick access
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <button
                            onClick={() => setShowInstall(false)}
                            style={{
                                padding: '8px 14px',
                                background: 'rgba(255,255,255,0.15)',
                                border: 'none',
                                borderRadius: 8,
                                color: '#fff',
                                fontWeight: 600,
                                cursor: 'pointer',
                                fontSize: 12,
                            }}
                        >
                            Later
                        </button>
                        <button
                            onClick={handleInstall}
                            style={{
                                padding: '8px 16px',
                                background: '#fff',
                                border: 'none',
                                borderRadius: 8,
                                color: '#047857',
                                fontWeight: 700,
                                cursor: 'pointer',
                                fontSize: 12,
                            }}
                        >
                            Install
                        </button>
                    </div>
                </div>
            )}

            {/* Nav */}
            <nav style={{ background: T.navy, padding: '0 48px', height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Link href="/" style={{ fontSize: 18, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px', textDecoration: 'none' }}>
                    Signal<span style={{ color: '#38BDF8' }}>Craft</span>
                </Link>
                <Link href="/" style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', textDecoration: 'none' }}>← Back to home</Link>
            </nav>

            {/* Card */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
                <div style={{ width: '100%', maxWidth: 400 }}>
                    <div style={{ background: '#fff', borderRadius: 16, border: `1px solid ${T.border}`, boxShadow: '0 4px 24px rgba(0,0,0,0.06)', padding: 40 }}>

                        <div style={{ textAlign: 'center', marginBottom: 32 }}>
                            <div style={{ fontSize: 22, fontWeight: 800, color: T.navy, marginBottom: 6 }}>Welcome back</div>
                            <div style={{ fontSize: 13, color: T.textMuted }}>Sign in to your SignalCraft account</div>
                        </div>

                        {error && (
                            <div style={{ background: T.redLight, border: `1px solid #FECACA`, borderRadius: 8, padding: '10px 14px', fontSize: 13, color: T.red, marginBottom: 20 }}>
                                {error}
                            </div>
                        )}

                        <form onSubmit={handleLogin}>
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
                                {loading ? 'Signing in...' : '⚡ Sign In'}
                            </button>
                        </form>

                        <div style={{ marginTop: 24, textAlign: 'center', fontSize: 12, color: T.textMuted }}>
                            Don't have an account?{' '}
                            <Link href="/register" style={{ color: T.blue, fontWeight: 600 }}>Create one</Link>
                        </div>
                    </div>

                    <div style={{ marginTop: 20, textAlign: 'center', fontSize: 11, color: T.textMuted, lineHeight: 1.6 }}>
                        SignalCraft is a personal trading tool. All data stays on your machine.
                    </div>
                </div>
            </div>

            <style dangerouslySetInnerHTML={{
                __html: `
                    @keyframes slideDown {
                        from {
                            opacity: 0;
                            transform: translateX(-50%) translateY(-30px);
                        }
                        to {
                            opacity: 1;
                            transform: translateX(-50%) translateY(0);
                        }
                    }
                `
            }} />
        </div>
    )
}
