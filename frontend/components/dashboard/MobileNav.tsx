'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { config } from '@/lib/config'
import { useState, useEffect } from 'react'

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
}

interface MobileNavProps {
    userName: string
}

export function MobileNav({ userName }: MobileNavProps) {
    const pathname = usePathname()
    const router = useRouter()
    const [showLogout, setShowLogout] = useState(false)
    const [showInstall, setShowInstall] = useState(false)
    const [deferredPrompt, setDeferredPrompt] = useState<any>(null)

    // Listen for PWA install prompt
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

    const handleInstall = async () => {
        if (!deferredPrompt) return
        deferredPrompt.prompt()
        const { outcome } = await deferredPrompt.userChoice
        if (outcome === 'accepted') {
            console.log('[PWA] User accepted')
        }
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
        { href: '/strategy', label: 'Strategies', icon: '📁' },
        { href: '/backtest', label: 'Backtest', icon: '📊' },
        { href: '/settings', label: 'Settings', icon: '⚙' },
    ]

    return (
        <>
            {/* PWA Install Banner - shows at top on mobile */}
            {showInstall && (
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
                        <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 2 }}>
                            Install SignalCraft
                        </div>
                        <div style={{ fontSize: 11, opacity: 0.9 }}>
                            Add to home screen
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                        <button
                            onClick={() => setShowInstall(false)}
                            style={{
                                padding: '6px 10px',
                                background: 'rgba(255,255,255,0.15)',
                                border: 'none',
                                borderRadius: 6,
                                color: '#fff',
                                fontWeight: 600,
                                cursor: 'pointer',
                                fontSize: 11,
                            }}
                        >
                            Later
                        </button>
                        <button
                            onClick={handleInstall}
                            style={{
                                padding: '6px 10px',
                                background: '#fff',
                                border: 'none',
                                borderRadius: 6,
                                color: '#047857',
                                fontWeight: 700,
                                cursor: 'pointer',
                                fontSize: 11,
                            }}
                        >
                            Install
                        </button>
                    </div>
                </div>
            )}

            <div style={{
                position: 'fixed',
                bottom: 0,
                left: 0,
                right: 0,
                background: '#FFFFFF',
                borderTop: `1px solid ${T.border}`,
                display: 'flex',
                justifyContent: 'space-around',
                alignItems: 'center',
                padding: '8px 0',
                paddingBottom: 'max(8px, env(safe-area-inset-bottom))',
                zIndex: 1000,
                boxShadow: '0 -2px 10px rgba(0,0,0,0.05)',
            }}>
                {navItems.map((item) => {
                    const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href))
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            style={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                gap: 2,
                                padding: '4px 8px',
                                textDecoration: 'none',
                                color: isActive ? T.blue : T.textMuted,
                                background: isActive ? T.blueLight : 'transparent',
                                borderRadius: 8,
                                transition: 'all 0.2s',
                                minWidth: 50,
                            }}
                        >
                            <span style={{ fontSize: 18 }}>{item.icon}</span>
                            <span style={{ fontSize: 10, fontWeight: 600 }}>{item.label}</span>
                        </Link>
                    )
                })}
                
                {/* Logout button */}
                <button
                    onClick={() => setShowLogout(true)}
                    style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 2,
                        padding: '4px 8px',
                        border: 'none',
                        background: 'transparent',
                        color: T.red,
                        borderRadius: 8,
                        transition: 'all 0.2s',
                        minWidth: 50,
                        cursor: 'pointer',
                    }}
                >
                    <span style={{ fontSize: 18 }}>🚪</span>
                    <span style={{ fontSize: 10, fontWeight: 600 }}>Logout</span>
                </button>
            </div>

            {/* Logout confirmation modal */}
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
                        background: '#fff',
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
                            <button 
                                onClick={() => setShowLogout(false)} 
                                style={{
                                    flex: 1, 
                                    padding: 12, 
                                    border: `1px solid ${T.border}`, 
                                    borderRadius: 8,
                                    background: '#fff', 
                                    fontSize: 14, 
                                    fontWeight: 600, 
                                    cursor: 'pointer', 
                                    color: T.text,
                                }}
                            >
                                Cancel
                            </button>
                            <button 
                                onClick={handleLogout} 
                                style={{
                                    flex: 1, 
                                    padding: 12, 
                                    border: 'none', 
                                    borderRadius: 8,
                                    background: T.red, 
                                    fontSize: 14, 
                                    fontWeight: 700, 
                                    cursor: 'pointer', 
                                    color: '#fff',
                                }}
                            >
                                Logout
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}

export function MobileHeader({ userName, onMenuClick }: { userName: string; onMenuClick?: () => void }) {
    return (
        <div style={{
            background: `linear-gradient(135deg, #0F2744, #1D4ED8)`,
            color: '#fff',
            padding: '16px 20px',
            paddingTop: 'max(16px, env(safe-area-inset-top))',
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
        }}>
            {/* Hamburger menu button */}
            <button
                onClick={onMenuClick}
                style={{
                    background: 'rgba(255,255,255,0.15)',
                    border: 'none',
                    borderRadius: 8,
                    padding: '8px 12px',
                    color: '#fff',
                    cursor: 'pointer',
                    fontSize: 20,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.25)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.15)'}
            >
                ☰
            </button>
            <div>
                <div style={{ fontSize: 12, opacity: 0.9, marginBottom: 2 }}>
                    Welcome back,
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.5px' }}>
                    {userName} 👋
                </div>
            </div>
        </div>
    )
}
