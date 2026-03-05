'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { config } from '@/lib/config'

const T = {
    navy: '#0F2744',
    blue: '#1D4ED8',
    blueLight: '#EFF6FF',
    border: '#E2E8F0',
    textMuted: '#94A3B8',
    textMid: '#475569',
    text: '#0F172A',
    red: '#DC2626',
    redLight: '#FEF2F2',
    admin: '#7C3AED',
    adminLight: '#F5F3FF',
}

export default function AdminLoginPage() {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)
    const router = useRouter()

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
            console.log('Login response:', data)

            if (!res.ok) {
                if (data.detail === 'Incorrect email or password') {
                    setError('Invalid admin credentials')
                } else {
                    setError(data.detail || 'Login failed')
                }
                return
            }

            // Check if user is admin
            console.log('User role:', data.user?.role)
            if (data.user?.role !== 'admin') {
                setError('Access denied. Admin privileges required.')
                return
            }

            // Store admin-specific token
            localStorage.setItem(config.authTokenKey, data.access_token)
            localStorage.setItem(config.authUserKey, JSON.stringify(data.user))
            localStorage.setItem('sc_admin', 'true')

            // Set cookies with proper path and SameSite attributes
            const cookieValue = `${config.authTokenKey}=${data.access_token}; path=/; max-age=${config.tokenMaxAgeDays * 60 * 60 * 24}; SameSite=Lax`
            document.cookie = cookieValue

            // Also set sc_admin cookie
            document.cookie = `sc_admin=true; path=/; max-age=${config.tokenMaxAgeDays * 60 * 60 * 24}; SameSite=Lax`

            console.log('Cookies set, redirecting to dashboard...')

            // Force a full page reload to ensure cookies are sent to server
            window.location.href = '/admin/dashboard'
        } catch {
            setError('Backend not reachable. Make sure the API is running.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div style={{
            minHeight: '100vh', display: 'flex', flexDirection: 'column',
            background: 'linear-gradient(135deg, #0F2744 0%, #1e1b4b 100%)',
            fontFamily: "'DM Sans', sans-serif",
        }}>
            {/* Nav */}
            <nav style={{
                padding: '20px 48px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
            }}>
                <Link href="/" style={{
                    fontSize: 20,
                    fontWeight: 800,
                    color: '#fff',
                    letterSpacing: '-0.5px',
                    textDecoration: 'none'
                }}>
                    Signal<span style={{ color: '#38BDF8' }}>Craft</span>
                </Link>
            </nav>

            {/* Login Card */}
            <div style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 24
            }}>
                <div style={{ width: '100%', maxWidth: 420 }}>
                    <div style={{
                        background: 'rgba(255, 255, 255, 0.98)',
                        borderRadius: 20,
                        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                        padding: 48
                    }}>
                        {/* Admin Badge */}
                        <div style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            background: T.adminLight,
                            color: T.admin,
                            borderRadius: 20,
                            padding: '6px 14px',
                            fontSize: 11,
                            fontWeight: 700,
                            letterSpacing: '0.8px',
                            textTransform: 'uppercase',
                            marginBottom: 24,
                        }}>
                            🔒 Admin Panel
                        </div>

                        <div style={{ textAlign: 'center', marginBottom: 32 }}>
                            <div style={{
                                fontSize: 26,
                                fontWeight: 800,
                                color: T.navy,
                                marginBottom: 8
                            }}>
                                Admin Access
                            </div>
                            <div style={{ fontSize: 14, color: T.textMuted }}>
                                Sign in with your admin credentials
                            </div>
                        </div>

                        {error && (
                            <div style={{
                                background: T.redLight,
                                border: `1px solid #FECACA`,
                                borderRadius: 10,
                                padding: '12px 16px',
                                fontSize: 13,
                                color: T.red,
                                marginBottom: 20,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8
                            }}>
                                <span>⚠️</span> {error}
                            </div>
                        )}

                        <form onSubmit={handleLogin}>
                            <div style={{ marginBottom: 18 }}>
                                <label style={{
                                    display: 'block',
                                    fontSize: 11,
                                    fontWeight: 700,
                                    color: T.textMid,
                                    marginBottom: 8,
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.5px'
                                }}>
                                    Admin Email
                                </label>
                                <input
                                    type="email"
                                    required
                                    value={email}
                                    onChange={e => setEmail(e.target.value)}
                                    placeholder="admin@signalcraft.com"
                                    style={{
                                        width: '100%',
                                        padding: '12px 14px',
                                        border: `1px solid ${T.border}`,
                                        borderRadius: 10,
                                        fontSize: 14,
                                        outline: 'none',
                                        fontFamily: "'DM Sans', sans-serif",
                                        transition: 'border-color 0.2s'
                                    }}
                                />
                            </div>
                            <div style={{ marginBottom: 24 }}>
                                <label style={{
                                    display: 'block',
                                    fontSize: 11,
                                    fontWeight: 700,
                                    color: T.textMid,
                                    marginBottom: 8,
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.5px'
                                }}>
                                    Password
                                </label>
                                <input
                                    type="password"
                                    required
                                    value={password}
                                    onChange={e => setPassword(e.target.value)}
                                    placeholder="••••••••••••"
                                    style={{
                                        width: '100%',
                                        padding: '12px 14px',
                                        border: `1px solid ${T.border}`,
                                        borderRadius: 10,
                                        fontSize: 14,
                                        outline: 'none',
                                        fontFamily: "'DM Sans', sans-serif",
                                        transition: 'border-color 0.2s'
                                    }}
                                />
                            </div>
                            <button
                                type="submit"
                                disabled={loading}
                                style={{
                                    width: '100%',
                                    padding: '14px',
                                    background: T.admin,
                                    color: '#fff',
                                    border: 'none',
                                    borderRadius: 10,
                                    fontSize: 14,
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    opacity: loading ? 0.7 : 1,
                                    transition: 'all 0.2s',
                                    boxShadow: '0 4px 14px rgba(124, 58, 237, 0.3)'
                                }}
                            >
                                {loading ? (
                                    <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                                        <span style={{
                                            width: 16,
                                            height: 16,
                                            border: `2px solid rgba(255,255,255,0.3)`,
                                            borderTopColor: '#fff',
                                            borderRadius: '50%',
                                            animation: 'spin 1s linear infinite'
                                        }} />
                                        Authenticating...
                                    </span>
                                ) : (
                                    '🔐 Admin Sign In'
                                )}
                            </button>
                        </form>

                        <div style={{
                            marginTop: 24,
                            padding: '16px',
                            background: T.blueLight,
                            borderRadius: 10,
                            fontSize: 12,
                            color: T.textMid,
                            lineHeight: 1.6
                        }}>
                            <strong>⚠️ Restricted Access:</strong> This panel is only accessible to authorized administrators.
                            All actions are logged and monitored.
                        </div>

                        <div style={{
                            marginTop: 20,
                            textAlign: 'center',
                            fontSize: 12,
                            color: T.textMuted,
                            paddingTop: 20,
                            borderTop: `1px solid ${T.border}`
                        }}>
                            Need to create first admin?{' '}
                            <br />
                            <code style={{
                                background: '#f1f5f9',
                                padding: '4px 8px',
                                borderRadius: 4,
                                fontSize: 11
                            }}>
                                python3 backend/scripts/create_admin.py
                            </code>
                        </div>
                    </div>
                </div>
            </div>

            <style>{`
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    )
}
