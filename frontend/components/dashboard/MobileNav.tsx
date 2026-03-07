'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const T = {
    navy: '#0F2744',
    blue: '#1D4ED8',
    blueLight: '#EFF6FF',
    border: '#E2E8F0',
    textMuted: '#94A3B8',
    text: '#0F172A',
    green: '#059669',
    greenLight: '#ECFDF5',
}

interface MobileNavProps {
    userName: string
}

export function MobileNav({ userName }: MobileNavProps) {
    const pathname = usePathname()

    const navItems = [
        { href: '/dashboard', label: 'Home', icon: '🏠' },
        { href: '/strategy/new', label: 'Build', icon: '⚡' },
        { href: '/backtest', label: 'Backtest', icon: '📊' },
        { href: '/live', label: 'Live', icon: '🔴' },
        { href: '/settings', label: 'Settings', icon: '⚙' },
    ]

    return (
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
            paddingBottom: 'env(safe-area-inset-bottom)',
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
                            padding: '4px 12px',
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
        </div>
    )
}

export function MobileHeader({ userName }: { userName: string }) {
    return (
        <div style={{
            background: `linear-gradient(135deg, #0F2744, #1D4ED8)`,
            color: '#fff',
            padding: '16px 20px',
            paddingTop: 'max(16px, env(safe-area-inset-top))',
            marginBottom: 16,
        }}>
            <div style={{ fontSize: 13, opacity: 0.9, marginBottom: 4 }}>
                Welcome back,
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: '-0.5px' }}>
                {userName} 👋
            </div>
        </div>
    )
}
