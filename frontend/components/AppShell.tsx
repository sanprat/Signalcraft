'use client'

import { useState, useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { BackButton } from './BackButton'
import { config } from '@/lib/config'

const T = {
    navy: '#0F2744',
    blue: '#1D4ED8',
    blueLight: '#EFF6FF',
    border: '#E2E8F0',
    textMuted: '#94A3B8',
    text: '#0F172A',
    green: '#059669',
    greenLight: '#ECFDF5',
    red: '#DC2626',
    redLight: '#FEF2F2',
    white: '#FFFFFF',
    bg: '#F8FAFC',
}

interface AppShellProps {
    children: React.ReactNode
    title?: string
    showBack?: boolean
    defaultBack?: string
    onRefresh?: () => Promise<void>
}

export function AppShell({ children, title, showBack = false, defaultBack = '/dashboard', onRefresh }: AppShellProps) {
    const pathname = usePathname()
    const router = useRouter()
    const [isMobile, setIsMobile] = useState(false)
    const [showLogout, setShowLogout] = useState(false)
    const [showInstall, setShowInstall] = useState(false)
    const [deferredPrompt, setDeferredPrompt] = useState<any>(null)
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [pullStartY, setPullStartY] = useState(0)
    const [pullDistance, setPullDistance] = useState(0)

    // Detect mobile
    useEffect(() => {
        const checkMobile = () => setIsMobile(window.innerWidth < 768)
        checkMobile()
        window.addEventListener('resize', checkMobile)
        return () => window.removeEventListener('resize', checkMobile)
    }, [])

    // PWA install prompt
    useEffect(() => {
        const handleBeforeInstallPrompt = (e: Event) => {
            e.preventDefault()
            setDeferredPrompt(e)
            setShowInstall(true)
        }
        const handleAppInstalled = () => {
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

    // Pull-to-refresh handlers
    useEffect(() => {
        if (!isMobile || !onRefresh) return

        const handleTouchStart = (e: TouchEvent) => {
            if (window.scrollY === 0) {
                setPullStartY(e.touches[0].clientY)
            }
        }

        const handleTouchMove = (e: TouchEvent) => {
            if (pullStartY === 0) return
            const currentY = e.touches[0].clientY
            const distance = currentY - pullStartY
            if (distance > 0 && window.scrollY === 0) {
                e.preventDefault()
                setPullDistance(Math.min(distance * 0.5, 100))
            }
        }

        const handleTouchEnd = async () => {
            if (pullDistance > 80 && onRefresh) {
                setIsRefreshing(true)
                await onRefresh()
                setIsRefreshing(false)
            }
            setPullStartY(0)
            setPullDistance(0)
        }

        document.addEventListener('touchstart', handleTouchStart, { passive: true })
        document.addEventListener('touchmove', handleTouchMove, { passive: false })
        document.addEventListener('touchend', handleTouchEnd)

        return () => {
            document.removeEventListener('touchstart', handleTouchStart)
            document.removeEventListener('touchmove', handleTouchMove)
            document.removeEventListener('touchend', handleTouchEnd)
        }
    }, [isMobile, onRefresh, pullStartY, pullDistance])

    const handleInstall = async () => {
        if (!deferredPrompt) return
        deferredPrompt.prompt()
        await deferredPrompt.userChoice
        setShowInstall(false)
        setDeferredPrompt(null)
    }

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

    const navItems = [
        { href: '/dashboard', label: 'Home', icon: '🏠' },
        { href: '/strategy/new', label: 'Build', icon: '⚡' },
        { href: '/backtest', label: 'Backtest', icon: '📊' },
        { href: '/live', label: 'Live', icon: '🔴' },
        { href: '/settings', label: 'Settings', icon: '⚙' },
    ]

    return (
        <div style={{
            minHeight: '100vh',
            background: T.bg,
            paddingBottom: isMobile ? 70 : 0,
        }}>
            {/* PWA Install Banner */}
            {showInstall && isMobile && (
                <div style={{
                    position: 'fixed',
                    top: 'max(16px, env(safe-area-inset-top))',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'linear-gradient(135deg, #10B981, #047857)',
                    color: '#fff',
                    padding: '12px 16px',
                    borderRadius: 12,
                    boxShadow: '0 4px 20px rgba(16, 185, 129, 0.3)',
                    zIndex: 10001,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    maxWidth: '90%',
                    width: 340,
                    animation: 'slideDown 0.3s ease-out',
                }}>
                    <div style={{ fontSize: 20 }}>📲</div>
                    <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 2 }}>Install SignalCraft</div>
                        <div style={{ fontSize: 11, opacity: 0.9 }}>Add to home screen</div>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                        <button onClick={() => setShowInstall(false)} style={{
                            padding: '6px 10px', background: 'rgba(255,255,255,0.15)', border: 'none',
                            borderRadius: 6, color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: 11,
                        }}>Later</button>
                        <button onClick={handleInstall} style={{
                            padding: '6px 10px', background: '#fff', border: 'none', borderRadius: 6,
                            color: '#047857', fontWeight: 700, cursor: 'pointer', fontSize: 11,
                        }}>Install</button>
                    </div>
                </div>
            )}

            {/* Pull-to-refresh indicator */}
            {isRefreshing && (
                <div style={{
                    position: 'fixed',
                    top: 60,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: T.white,
                    padding: '8px 16px',
                    borderRadius: 20,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                    zIndex: 9999,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 13,
                    fontWeight: 600,
                    color: T.text,
                }}>
                    <span style={{ animation: 'spin 1s linear infinite' }}>🔄</span>
                    Refreshing...
                </div>
            )}

            {/* Mobile App Header */}
            {isMobile && (
                <header style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: 56,
                    background: `linear-gradient(135deg, ${T.navy}, ${T.blue})`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0 16px',
                    paddingTop: 'max(0px, env(safe-area-inset-top))',
                    zIndex: 1000,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
                        {showBack ? (
                            <div style={{ transform: 'scale(0.85)', transformOrigin: 'left' }}>
                                <BackButton defaultBack={defaultBack} />
                            </div>
                        ) : (
                            <div style={{
                                width: 36,
                                height: 36,
                                borderRadius: 10,
                                background: 'rgba(255,255,255,0.15)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: 18,
                                fontWeight: 900,
                                color: '#fff',
                            }}>
                                SC
                            </div>
                        )}
                        {title && (
                            <h1 style={{
                                fontSize: 17,
                                fontWeight: 700,
                                color: '#fff',
                                margin: 0,
                                letterSpacing: '-0.3px',
                            }}>
                                {title}
                            </h1>
                        )}
                    </div>
                    <button
                        onClick={() => setShowLogout(true)}
                        style={{
                            background: 'rgba(255,255,255,0.15)',
                            border: 'none',
                            borderRadius: 8,
                            padding: '8px 12px',
                            color: '#fff',
                            cursor: 'pointer',
                            fontSize: 18,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            transition: 'background 0.2s',
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.25)'}
                        onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.15)'}
                    >
                        🚪
                    </button>
                </header>
            )}

            {/* Content */}
            <main style={{
                paddingTop: isMobile ? 56 : 0,
                minHeight: '100vh',
            }}>
                {children}
            </main>

            {/* Mobile Bottom Tab Bar */}
            {isMobile && (
                <nav style={{
                    position: 'fixed',
                    bottom: 0,
                    left: 0,
                    right: 0,
                    height: 'max(60px, env(safe-area-inset-bottom))',
                    background: T.white,
                    borderTop: `1px solid ${T.border}`,
                    display: 'flex',
                    justifyContent: 'space-around',
                    alignItems: 'flex-start',
                    paddingTop: 8,
                    paddingBottom: 'max(0px, env(safe-area-inset-bottom))',
                    zIndex: 1000,
                    boxShadow: '0 -2px 10px rgba(0,0,0,0.05)',
                }}>
                    {navItems.map((item) => {
                        const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href))
                        return (
                            <button
                                key={item.href}
                                onClick={() => router.push(item.href)}
                                style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: 4,
                                    padding: '4px 8px',
                                    border: 'none',
                                    background: 'transparent',
                                    color: isActive ? T.blue : T.textMuted,
                                    borderRadius: 8,
                                    transition: 'all 0.2s',
                                    minWidth: 56,
                                    cursor: 'pointer',
                                }}
                            >
                                <span style={{ fontSize: 20 }}>{item.icon}</span>
                                <span style={{ fontSize: 10, fontWeight: 600 }}>{item.label}</span>
                                {isActive && (
                                    <div style={{
                                        width: 4,
                                        height: 4,
                                        borderRadius: '50%',
                                        background: T.blue,
                                        marginTop: 2,
                                    }} />
                                )}
                            </button>
                        )
                    })}
                </nav>
            )}

            {/* Logout Modal */}
            {showLogout && (
                <div style={{
                    position: 'fixed',
                    inset: 0,
                    background: 'rgba(0,0,0,0.6)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 10000,
                    padding: 20,
                }}>
                    <div style={{
                        background: T.white,
                        borderRadius: 16,
                        padding: 24,
                        maxWidth: 320,
                        width: '100%',
                        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
                    }}>
                        <div style={{ fontSize: 32, textAlign: 'center', marginBottom: 12 }}>🚪</div>
                        <h3 style={{ margin: '0 0 8px', textAlign: 'center', color: T.text, fontSize: 18, fontWeight: 700 }}>
                            Logout?
                        </h3>
                        <p style={{ textAlign: 'center', color: T.textMuted, fontSize: 13, margin: '0 0 20px', lineHeight: 1.5 }}>
                            Are you sure you want to logout from SignalCraft?
                        </p>
                        <div style={{ display: 'flex', gap: 10 }}>
                            <button onClick={() => setShowLogout(false)} style={{
                                flex: 1, padding: 12, border: `1px solid ${T.border}`, borderRadius: 8,
                                background: T.white, fontSize: 14, fontWeight: 600, cursor: 'pointer', color: T.text,
                            }}>Cancel</button>
                            <button onClick={handleLogout} style={{
                                flex: 1, padding: 12, border: 'none', borderRadius: 8,
                                background: T.red, fontSize: 14, fontWeight: 700, cursor: 'pointer', color: '#fff',
                            }}>Logout</button>
                        </div>
                    </div>
                </div>
            )}

            <style jsx global>{`
                @keyframes slideDown {
                    from { opacity: 0; transform: translateX(-50%) translateY(-20px); }
                    to { opacity: 1; transform: translateX(-50%) translateY(0); }
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    )
}
