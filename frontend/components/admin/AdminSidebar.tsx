'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const T = {
    navy: '#0F2744',
    blue: '#1D4ED8',
    blueLight: '#EFF6FF',
    border: '#E2E8F0',
    textMuted: '#94A3B8',
    textMid: '#475569',
    text: '#0F172A',
    admin: '#7C3AED',
    adminLight: '#F5F3FF',
    surface: '#FFFFFF',
    surfaceHover: '#F1F5F9',
}

interface SidebarProps {
    children: React.ReactNode
}

export function AdminSidebar({ children }: SidebarProps) {
    const pathname = usePathname()
    
    const navItems = [
        { label: 'Dashboard', href: '/admin/dashboard', icon: '📊' },
        { label: 'Users', href: '/admin/users', icon: '👥' },
        { label: 'Strategies', href: '/admin/strategies', icon: '⚡' },
        { label: 'Activity Logs', href: '/admin/logs', icon: '📝' },
    ]
    
    const isActive = (href: string) => pathname === href
    
    return (
        <div style={{
            display: 'flex',
            minHeight: '100vh',
            background: '#F8FAFC',
        }}>
            {/* Sidebar */}
            <aside style={{
                width: 260,
                background: T.navy,
                padding: 24,
                display: 'flex',
                flexDirection: 'column',
                position: 'sticky',
                top: 0,
                height: '100vh',
                overflowY: 'auto',
            }}>
                {/* Logo */}
                <Link href="/admin/dashboard" style={{
                    fontSize: 20,
                    fontWeight: 800,
                    color: '#fff',
                    letterSpacing: '-0.5px',
                    textDecoration: 'none',
                    marginBottom: 32,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                }}>
                    <span>🔐</span>
                    Signal<span style={{ color: '#38BDF8' }}>Craft</span>
                </Link>
                
                {/* Admin Badge */}
                <div style={{
                    background: 'rgba(255,255,255,0.1)',
                    borderRadius: 10,
                    padding: '12px 14px',
                    marginBottom: 24,
                }}>
                    <div style={{
                        fontSize: 10,
                        color: 'rgba(255,255,255,0.5)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.8px',
                        fontWeight: 700,
                        marginBottom: 4,
                    }}>
                        Admin Panel
                    </div>
                    <div style={{
                        fontSize: 13,
                        color: '#fff',
                        fontWeight: 600,
                    }}>
                        Management Console
                    </div>
                </div>
                
                {/* Navigation */}
                <nav style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
                    {navItems.map(item => {
                        const active = isActive(item.href)
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 12,
                                    padding: '12px 14px',
                                    borderRadius: 10,
                                    fontSize: 13,
                                    fontWeight: 600,
                                    textDecoration: 'none',
                                    transition: 'all 0.15s',
                                    background: active ? T.admin : 'transparent',
                                    color: active ? '#fff' : 'rgba(255,255,255,0.7)',
                                }}
                            >
                                <span style={{ fontSize: 16 }}>{item.icon}</span>
                                {item.label}
                            </Link>
                        )
                    })}
                </nav>
                
                {/* Back to Site */}
                <div style={{
                    paddingTop: 16,
                    borderTop: `1px solid rgba(255,255,255,0.1)`,
                }}>
                    <Link
                        href="/dashboard"
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 10,
                            padding: '12px 14px',
                            borderRadius: 10,
                            fontSize: 13,
                            fontWeight: 600,
                            textDecoration: 'none',
                            color: 'rgba(255,255,255,0.6)',
                            transition: 'all 0.15s',
                        }}
                    >
                        <span>→</span>
                        Back to User Site
                    </Link>
                </div>
            </aside>
            
            {/* Main Content */}
            <main style={{
                flex: 1,
                padding: 32,
                overflowY: 'auto',
            }}>
                {children}
            </main>
        </div>
    )
}
