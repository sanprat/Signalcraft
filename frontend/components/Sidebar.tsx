'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { config } from '@/lib/config'

const T = {
    navy: '#0F2744',
    blue: '#38BDF8',
    green: '#059669',
    red: '#DC2626',
    redLight: 'rgba(220,38,38,0.15)',
    redBorder: 'rgba(220,38,38,0.3)',
    redText: '#FCA5A5',
    border: 'rgba(255,255,255,0.08)',
    activeBg: 'rgba(56,189,248,0.15)',
    activeText: '#38BDF8',
    inactiveText: 'rgba(255,255,255,0.55)',
}

const navItems = [
    { id: 'dashboard', href: '/dashboard', label: 'Dashboard', icon: '⊞' },
    { id: 'builder', href: '/strategy/new', label: 'Strategy Builder', icon: '⚡' },
    { id: 'backtest', href: '/backtest', label: 'Backtests', icon: '↩' },
    { id: 'live', href: '/live', label: 'Live Trading', icon: '◉' },
    { id: 'settings', href: '/settings', label: 'Settings', icon: '⚙' },
]

export default function Sidebar() {
    const pathname = usePathname()
    const router = useRouter()
    const searchParams = useSearchParams()

    const currentSegment = searchParams.get('segment') || 'Options'

    const handleSegmentChange = (seg: string) => {
        const params = new URLSearchParams(searchParams.toString())
        params.set('segment', seg)
        router.push(`${pathname}?${params.toString()}`)
    }
    const [emergencyModal, setEmergencyModal] = useState(false)
    const [user, setUser] = useState<{ email: string; full_name?: string } | null>(null)
    const liveCount = 1 // TODO: fetch from API

    const handleLogout = async () => {
        try {
            await fetch(`${config.apiBaseUrl}/api/auth/logout`, { method: 'POST' })
        } catch (e) {
            console.error('Logout error:', e)
        }
        localStorage.removeItem(config.authTokenKey)
        localStorage.removeItem(config.authUserKey)
        localStorage.removeItem('sc_admin')
        document.cookie = `${config.authTokenKey}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`
        document.cookie = `sc_admin=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`
        router.push('/login')
    }

    useEffect(() => {
        // Get user from localStorage
        const storedUser = localStorage.getItem('sc_user')
        if (storedUser) {
            try {
                setUser(JSON.parse(storedUser))
            } catch (e) {
                console.error('Failed to parse user from localStorage', e)
            }
        }
    }, [])

    const userEmail = user?.full_name || user?.email?.split('@')[0] || 'User'
    const userInitial = user?.full_name?.[0] || user?.email?.[0]?.toUpperCase() || 'U'

    return (
        <>
            <aside style={{
                width: 220, background: T.navy, display: 'flex', flexDirection: 'column',
                flexShrink: 0, borderRight: `1px solid ${T.border}`, height: '100vh',
            }}>
                {/* Logo */}
                <div style={{ padding: '24px 20px 20px', borderBottom: `1px solid ${T.border}` }}>
                    <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px' }}>
                        Signal<span style={{ color: T.blue }}>Craft</span>
                    </div>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginTop: 2, letterSpacing: '1px', textTransform: 'uppercase' }}>
                        Craft your trading signals
                    </div>
                </div>

                {/* Segment toggle */}
                <div style={{ padding: '14px 16px', borderBottom: `1px solid ${T.border}` }}>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: '0.8px', textTransform: 'uppercase', marginBottom: 8 }}>Segment</div>
                    <div style={{ display: 'flex', background: 'rgba(255,255,255,0.06)', borderRadius: 8, padding: 3 }}>
                        {['Options', 'Stocks'].map(seg => (
                            <button
                                key={seg}
                                onClick={() => handleSegmentChange(seg)}
                                style={{
                                    flex: 1, padding: '5px 0', border: 'none', borderRadius: 6,
                                    fontSize: 12, fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s',
                                    background: seg === currentSegment ? 'rgba(255,255,255,0.12)' : 'transparent',
                                    color: seg === currentSegment ? '#fff' : 'rgba(255,255,255,0.4)',
                                }}
                            >
                                {seg}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Nav */}
                <nav style={{ flex: 1, padding: '12px 10px' }}>
                    {navItems.map(item => {
                        const active = pathname === item.href || (item.href !== '/dashboard' && item.href !== '/' && pathname.startsWith(item.href))
                        return (
                            <Link key={item.id} href={item.href} style={{
                                width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                                padding: '9px 12px', border: 'none', borderRadius: 8, cursor: 'pointer',
                                textAlign: 'left', marginBottom: 2, transition: 'all 0.15s', textDecoration: 'none',
                                background: active ? T.activeBg : 'transparent',
                                color: active ? T.activeText : T.inactiveText,
                                fontSize: 13, fontWeight: active ? 600 : 400,
                            }}>
                                <span style={{ fontSize: 15 }}>{item.icon}</span>
                                {item.label}
                                {item.id === 'live' && liveCount > 0 && (
                                    <span style={{
                                        marginLeft: 'auto', background: T.green, color: '#fff',
                                        borderRadius: 10, padding: '1px 6px', fontSize: 10, fontWeight: 700,
                                    }}>{liveCount}</span>
                                )}
                            </Link>
                        )
                    })}
                </nav>

                {/* Emergency stop */}
                <div style={{ padding: '14px 16px', borderTop: `1px solid ${T.border}` }}>
                    <button onClick={() => setEmergencyModal(true)} style={{
                        width: '100%', padding: 9, background: T.redLight,
                        border: `1px solid ${T.redBorder}`, borderRadius: 8,
                        color: T.redText, fontSize: 12, fontWeight: 700, cursor: 'pointer', letterSpacing: '0.3px',
                    }}>⏹ Emergency Stop All</button>
                </div>

                {/* User */}
                <div style={{
                    padding: '14px 16px', borderTop: `1px solid ${T.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{
                            width: 32, height: 32, borderRadius: '50%', background: 'rgba(56,189,248,0.2)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 13, fontWeight: 700, color: T.blue,
                        }}>{userInitial}</div>
                        <div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: '#fff' }}>{userEmail}</div>
                            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>User</div>
                        </div>
                    </div>
                    <button
                        onClick={handleLogout}
                        title="Logout"
                        style={{
                            background: 'transparent',
                            border: 'none',
                            color: 'rgba(255,255,255,0.5)',
                            cursor: 'pointer',
                            fontSize: '18px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '4px',
                            borderRadius: '4px',
                            transition: 'color 0.2s',
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.color = T.redText; e.currentTarget.style.background = 'rgba(255,255,255,0.05)' }}
                        onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.5)'; e.currentTarget.style.background = 'transparent' }}
                    >
                        ⎋
                    </button>
                </div>
            </aside>

            {/* Emergency modal */}
            {emergencyModal && (
                <div style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
                }}>
                    <div style={{
                        background: '#fff', borderRadius: 16, padding: 32, maxWidth: 380, width: '90%',
                        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
                    }}>
                        <div style={{ fontSize: 40, textAlign: 'center', marginBottom: 12 }}>⏹</div>
                        <h2 style={{ margin: '0 0 8px', textAlign: 'center', color: '#DC2626', fontSize: 20, fontWeight: 800 }}>
                            Emergency Stop All?
                        </h2>
                        <p style={{ textAlign: 'center', color: '#475569', fontSize: 13, margin: '0 0 24px', lineHeight: 1.5 }}>
                            This will <strong>immediately exit all open positions</strong> and stop all {liveCount} active strategies. This cannot be undone.
                        </p>
                        <div style={{ display: 'flex', gap: 10 }}>
                            <button onClick={() => setEmergencyModal(false)} style={{
                                flex: 1, padding: 12, border: '1px solid #E2E8F0', borderRadius: 8,
                                background: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', color: '#475569',
                            }}>Cancel</button>
                            <button onClick={() => setEmergencyModal(false)} style={{
                                flex: 1, padding: 12, border: 'none', borderRadius: 8,
                                background: '#DC2626', fontSize: 13, fontWeight: 700, cursor: 'pointer', color: '#fff',
                            }}>Yes, Stop All</button>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}
