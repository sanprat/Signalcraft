'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { config } from '@/lib/config'

const T = {
    navy: '#0F2744',
    blue: '#38BDF8',
    border: 'rgba(255,255,255,0.1)',
    activeBg: 'rgba(56,189,248,0.1)',
    activeText: '#38BDF8',
    inactiveText: 'rgba(255,255,255,0.7)',
    redText: '#FCA5A5',
}

const navItems = [
    { id: 'dashboard', href: '/dashboard', label: 'Dashboard', icon: '⊞' },
    { id: 'builder', href: '/strategy/new', label: 'Strategy Builder', icon: '⚡' },
    { id: 'strategies', href: '/strategy', label: 'My Strategies', icon: '⊡' },
    { id: 'backtest', href: '/backtest', label: 'Backtests', icon: '↩' },
    { id: 'settings', href: '/settings', label: 'Settings', icon: '⚙' },
]

export default function TopNavbar() {
    const pathname = usePathname()
    const router = useRouter()
    const [user, setUser] = useState<{ email: string; full_name?: string } | null>(null)
    const [dropdownOpen, setDropdownOpen] = useState(false)

    useEffect(() => {
        const storedUser = localStorage.getItem('sc_user')
        if (storedUser) {
            try {
                setUser(JSON.parse(storedUser))
            } catch (e) {
                console.error('Failed to parse user from localStorage', e)
            }
        }
    }, [])

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

    const userEmail = user?.full_name || user?.email?.split('@')[0] || 'User'
    const userInitial = user?.full_name?.[0] || user?.email?.[0]?.toUpperCase() || 'U'

    // Only show navbar on specific paths
    const PUBLIC_PATHS = ['/', '/login', '/register', '/pricing']
    if (PUBLIC_PATHS.includes(pathname) || pathname?.startsWith('/admin')) {
        return null
    }

    return (
        <header style={{
            height: 64,
            background: T.navy,
            borderBottom: `1px solid ${T.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
            position: 'sticky',
            top: 0,
            zIndex: 100,
        }}>
            {/* Logo */}
            <Link href="/dashboard" style={{ textDecoration: 'none', display: 'flex', flexDirection: 'column' }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px' }}>
                    Signal<span style={{ color: T.blue }}>Craft</span>
                </div>
                <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.4)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                    Strategy Engine
                </div>
            </Link>

            {/* Nav Links */}
            <nav style={{ display: 'flex', gap: 8, height: '100%', alignItems: 'center' }}>
                {navItems.map(item => {
                    const active = pathname === item.href || (item.href !== '/dashboard' && item.href !== '/' && pathname.startsWith(item.href))
                    return (
                        <Link key={item.id} href={item.href} style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            padding: '8px 16px',
                            borderRadius: 8,
                            textDecoration: 'none',
                            transition: 'all 0.2s',
                            background: active ? T.activeBg : 'transparent',
                            color: active ? T.activeText : T.inactiveText,
                            fontSize: 14,
                            fontWeight: active ? 600 : 500,
                        }}>
                            <span style={{ fontSize: 16 }}>{item.icon}</span>
                            {item.label}
                        </Link>
                    )
                })}
            </nav>

            {/* User Profile */}
            <div style={{ position: 'relative' }}>
                <button
                    onClick={() => setDropdownOpen(!dropdownOpen)}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        padding: '4px 8px',
                        borderRadius: 8,
                        transition: 'background 0.2s',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                >
                    <div style={{
                        width: 32,
                        height: 32,
                        borderRadius: '50%',
                        background: 'rgba(56,189,248,0.2)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 13,
                        fontWeight: 700,
                        color: T.blue,
                    }}>
                        {userInitial}
                    </div>
                    <div style={{ textAlign: 'left' }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>{userEmail}</div>
                    </div>
                    <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 10 }}>▼</span>
                </button>

                {dropdownOpen && (
                    <div style={{
                        position: 'absolute',
                        top: '120%',
                        right: 0,
                        width: 180,
                        background: '#1E293B',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: 12,
                        boxShadow: '0 10px 25px -5px rgba(0,0,0,0.3)',
                        padding: 8,
                        zIndex: 110,
                    }}>
                        <div style={{ padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.05)', marginBottom: 4 }}>
                            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>Logged in as</div>
                            <div style={{ fontSize: 13, color: '#fff', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>{userEmail}</div>
                        </div>
                        <button
                            onClick={handleLogout}
                            style={{
                                width: '100%',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 10,
                                padding: '10px 12px',
                                background: 'transparent',
                                border: 'none',
                                borderRadius: 8,
                                color: '#F87171',
                                fontSize: 13,
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'background 0.2s',
                            }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(248,113,113,0.1)' }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                        >
                            <span style={{ fontSize: 16 }}>⎋</span>
                            Logout
                        </button>
                    </div>
                )}
            </div>
        </header>
    )
}
