'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { config } from '@/lib/config'
import { AdminSidebar } from '@/components/admin/AdminSidebar'

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
    green: '#059669',
    greenLight: '#ECFDF5',
    red: '#DC2626',
    redLight: '#FEF2F2',
    amber: '#D97706',
    amberLight: '#FFFBEB',
}

interface Stats {
    total_users: number
    active_users: number
    admin_users: number
    inactive_users: number
    total_strategies: number
    live_strategies: number
}

export default function AdminDashboardPage() {
    const router = useRouter()
    const [stats, setStats] = useState<Stats | null>(null)
    const [loading, setLoading] = useState(true)
    const [adminName, setAdminName] = useState('Admin')

    useEffect(() => {
        // Check admin authentication
        const isAdmin = localStorage.getItem('sc_admin')
        const userStr = localStorage.getItem(config.authUserKey)

        if (!isAdmin) {
            router.push('/admin/login')
            return
        }

        if (userStr) {
            try {
                const user = JSON.parse(userStr)
                setAdminName(user.full_name || user.email.split('@')[0])
            } catch { }
        }

        // Fetch stats
        fetchStats()
    }, [])

    const fetchStats = async () => {
        try {
            const token = localStorage.getItem(config.authTokenKey)
            const res = await fetch(`${config.apiBaseUrl}/api/admin/stats`, {
                headers: { Authorization: `Bearer ${token}` }
            })
            if (res.ok) {
                const data = await res.json()
                setStats(data)
            } else if (res.status === 401) {
                handleLogout()
            }
        } catch (error) {
            console.error('Failed to fetch stats:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleLogout = async () => {
        try {
            await fetch(`${config.apiBaseUrl}/api/auth/logout`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${localStorage.getItem(config.authTokenKey)}` }
            })
        } catch { }
        localStorage.removeItem(config.authTokenKey)
        localStorage.removeItem(config.authUserKey)
        localStorage.removeItem('sc_admin')
        document.cookie = `${config.authTokenKey}=; path=/; max-age=0`
        router.push('/admin/login')
    }

    const StatCard = ({ title, value, sub, icon, color }: any) => (
        <div style={{
            background: T.surface,
            borderRadius: 16,
            border: `1px solid ${T.border}`,
            padding: 24,
            boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div style={{ fontSize: 11, color: T.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    {title}
                </div>
                <span style={{ fontSize: 20 }}>{icon}</span>
            </div>
            <div style={{ fontSize: 32, fontWeight: 800, color: color || T.text, letterSpacing: '-1px' }}>
                {loading ? '—' : value?.toLocaleString()}
            </div>
            {sub && (
                <div style={{ fontSize: 12, color: T.textMuted, marginTop: 6 }}>
                    {sub}
                </div>
            )}
        </div>
    )

    return (
        <AdminSidebar>
            {/* Header */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 32,
            }}>
                <div>
                    <h1 style={{
                        margin: 0,
                        fontSize: 26,
                        fontWeight: 800,
                        color: T.navy,
                        letterSpacing: '-0.5px',
                    }}>
                        Admin Dashboard
                    </h1>
                    <p style={{
                        margin: '6px 0 0',
                        fontSize: 14,
                        color: T.textMuted,
                    }}>
                        Welcome back, {adminName} 👋
                    </p>
                </div>
                <button
                    onClick={handleLogout}
                    style={{
                        padding: '10px 20px',
                        background: '#fff',
                        border: `1px solid ${T.border}`,
                        borderRadius: 10,
                        fontSize: 13,
                        fontWeight: 600,
                        color: T.textMid,
                        cursor: 'pointer',
                    }}
                >
                    Logout
                </button>
            </div>

            {/* Stats Grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 16,
                marginBottom: 32,
            }}>
                <StatCard
                    title="Total Users"
                    value={stats?.total_users}
                    sub={`${stats?.active_users} active · ${stats?.inactive_users} inactive`}
                    icon="👥"
                    color={T.blue}
                />
                <StatCard
                    title="Admin Users"
                    value={stats?.admin_users}
                    sub="Platform administrators"
                    icon="🔐"
                    color={T.admin}
                />
                <StatCard
                    title="Total Strategies"
                    value={stats?.total_strategies}
                    sub={`${stats?.live_strategies} currently live`}
                    icon="⚡"
                    color={T.amber}
                />
                <StatCard
                    title="Platform Health"
                    value="98%"
                    sub="All systems operational"
                    icon="✅"
                    color={T.green}
                />
            </div>

            {/* Quick Actions */}
            <div style={{
                background: T.surface,
                borderRadius: 16,
                border: `1px solid ${T.border}`,
                padding: 24,
                marginBottom: 20,
            }}>
                <h2 style={{
                    margin: '0 0 16px',
                    fontSize: 14,
                    fontWeight: 700,
                    color: T.textMid,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                }}>
                    Quick Actions
                </h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                    <Link
                        href="/admin/users"
                        style={{
                            padding: '16px',
                            background: T.blueLight,
                            borderRadius: 12,
                            textDecoration: 'none',
                            color: T.blue,
                            fontWeight: 600,
                            fontSize: 13,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 10,
                            transition: 'all 0.15s',
                        }}
                    >
                        <span style={{ fontSize: 18 }}>👥</span>
                        Manage Users
                    </Link>
                    <Link
                        href="/admin/logs"
                        style={{
                            padding: '16px',
                            background: T.adminLight,
                            borderRadius: 12,
                            textDecoration: 'none',
                            color: T.admin,
                            fontWeight: 600,
                            fontSize: 13,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 10,
                            transition: 'all 0.15s',
                        }}
                    >
                        <span style={{ fontSize: 18 }}>📝</span>
                        View Activity Logs
                    </Link>
                    <Link
                        href="/dashboard"
                        style={{
                            padding: '16px',
                            background: T.greenLight,
                            borderRadius: 12,
                            textDecoration: 'none',
                            color: T.green,
                            fontWeight: 600,
                            fontSize: 13,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 10,
                            transition: 'all 0.15s',
                        }}
                    >
                        <span style={{ fontSize: 18 }}>🚀</span>
                        Go to User Site
                    </Link>
                </div>
            </div>

            {/* Recent Activity Placeholder */}
            <div style={{
                background: T.surface,
                borderRadius: 16,
                border: `1px solid ${T.border}`,
                padding: 24,
            }}>
                <h2 style={{
                    margin: '0 0 16px',
                    fontSize: 14,
                    fontWeight: 700,
                    color: T.textMid,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                }}>
                    Recent Admin Activity
                </h2>
                <div style={{
                    padding: 40,
                    textAlign: 'center',
                    color: T.textMuted,
                    fontSize: 13,
                }}>
                    <span style={{ fontSize: 32, display: 'block', marginBottom: 8 }}>📝</span>
                    Activity logs will appear here
                    <br />
                    <Link href="/admin/logs" style={{ color: T.admin, fontWeight: 600 }}>
                        View all logs →
                    </Link>
                </div>
            </div>
        </AdminSidebar>
    )
}
