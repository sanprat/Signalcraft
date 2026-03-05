'use client'

import { useState } from 'react'
import { config } from '@/lib/config'

const T = {
    navy: '#0F2744',
    blue: '#1D4ED8',
    blueLight: '#EFF6FF',
    border: '#E2E8F0',
    borderStrong: '#CBD5E1',
    textMuted: '#94A3B8',
    textMid: '#475569',
    text: '#0F172A',
    admin: '#7C3AED',
    adminLight: '#F5F3FF',
    surface: '#FFFFFF',
    surfaceHover: '#F1F5F9',
    green: '#059669',
    greenLight: '#ECFDF5',
    greenMid: '#A7F3D0',
    red: '#DC2626',
    redLight: '#FEF2F2',
    redMid: '#FECACA',
    amber: '#D97706',
    amberLight: '#FFFBEB',
}

interface User {
    id: number
    email: string
    full_name: string | null
    role: string
    is_active: boolean
    created_at: string
}

interface UserTableProps {
    users: User[]
    onLoadMore: () => void
    onUserUpdated: () => void
}

export function UserTable({ users, onLoadMore, onUserUpdated }: UserTableProps) {
    const [loading, setLoading] = useState(false)
    const handleDelete = async (userId: number, email: string) => {
        if (!confirm(`Are you sure you want to delete user ${email}? This action cannot be undone.`)) {
            return
        }

        setLoading(true)
        try {
            const token = localStorage.getItem(config.authTokenKey)
            const res = await fetch(`${config.apiBaseUrl}/api/admin/users/${userId}`, {
                method: 'DELETE',
                headers: { Authorization: `Bearer ${token}` },
            })

            if (res.ok) {
                onUserUpdated()
            } else if (res.status === 401) {
                localStorage.removeItem(config.authTokenKey)
                localStorage.removeItem('sc_admin')
                window.location.href = '/admin/login'
            }
        } catch (error) {
            console.error('Failed to delete user:', error)
        } finally {
            setLoading(false)
        }
    }

    const RoleBadge = ({ role }: { role: string }) => (
        <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '4px 10px',
            borderRadius: 20,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.5px',
            textTransform: 'uppercase',
            background: role === 'admin' ? T.adminLight : T.blueLight,
            color: role === 'admin' ? T.admin : T.blue,
        }}>
            {role === 'admin' ? '🔐 Admin' : '👤 User'}
        </span>
    )

    const StatusBadge = ({ isActive }: { isActive: boolean }) => (
        <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 20,
            fontSize: 11,
            fontWeight: 600,
            background: isActive ? T.greenLight : T.redLight,
            color: isActive ? T.green : T.red,
        }}>
            <span style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: isActive ? T.green : T.red,
            }} />
            {isActive ? 'Active' : 'Inactive'}
        </span>
    )

    if (users.length === 0) {
        return (
            <div style={{
                padding: 60,
                textAlign: 'center',
                color: T.textMuted,
            }}>
                <span style={{ fontSize: 48, display: 'block', marginBottom: 16 }}>👥</span>
                No users found
            </div>
        )
    }

    return (
        <div style={{
            background: T.surface,
            borderRadius: 16,
            border: `1px solid ${T.border}`,
            overflow: 'hidden',
        }}>
            {/* Table Header */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: '2fr 1.5fr 1fr 1fr 120px',
                gap: 16,
                padding: '14px 20px',
                background: '#F8FAFC',
                borderBottom: `1px solid ${T.border}`,
                fontSize: 11,
                fontWeight: 700,
                color: T.textMid,
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
            }}>
                <div>Email</div>
                <div>Full Name</div>
                <div>Role</div>
                <div>Status</div>
                <div>Actions</div>
            </div>

            {/* Table Body */}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
                {users.map((user, index) => (
                    <div
                        key={user.id}
                        style={{
                            display: 'grid',
                            gridTemplateColumns: '2fr 1.5fr 1fr 1fr 120px',
                            gap: 16,
                            padding: '16px 20px',
                            borderBottom: index < users.length - 1 ? `1px solid ${T.border}` : 'none',
                            alignItems: 'center',
                            transition: 'background 0.15s',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceHover)}
                        onMouseLeave={(e) => (e.currentTarget.style.background = T.surface)}
                    >
                        {/* Email */}
                        <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>
                            {user.email}
                        </div>

                        {/* Full Name */}
                        <div style={{ fontSize: 13, color: T.textMid }}>
                            {user.full_name || '—'}
                        </div>

                        {/* Role */}
                        <div>
                            <RoleBadge role={user.role} />
                        </div>

                        {/* Status */}
                        <div>
                            <StatusBadge isActive={user.is_active} />
                        </div>

                        {/* Actions */}
                        <div style={{ display: 'flex', gap: 6 }}>
                            {user.role !== 'admin' ? (
                                <button
                                    onClick={() => handleDelete(user.id, user.email)}
                                    disabled={loading}
                                    style={{
                                        padding: '6px 10px',
                                        background: T.redLight,
                                        border: `1px solid ${T.redMid}`,
                                        borderRadius: 6,
                                        fontSize: 11,
                                        fontWeight: 600,
                                        cursor: 'pointer',
                                        color: T.red,
                                    }}
                                >
                                    🗑️ Delete
                                </button>
                            ) : (
                                <span style={{ fontSize: 11, color: T.textMuted, fontStyle: 'italic' }}>
                                    Protected
                                </span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
