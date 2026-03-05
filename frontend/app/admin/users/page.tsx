'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { config } from '@/lib/config'
import { AdminSidebar } from '@/components/admin/AdminSidebar'
import { UserTable } from '@/components/admin/UserTable'

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
}

interface User {
    id: number
    email: string
    full_name: string | null
    role: string
    is_active: boolean
    created_at: string
}

export default function AdminUsersPage() {
    const router = useRouter()
    const [users, setUsers] = useState<User[]>([])
    const [loading, setLoading] = useState(true)
    const [offset, setOffset] = useState(0)
    const [limit] = useState(50)
    const [hasMore, setHasMore] = useState(true)

    useEffect(() => {
        const isAdmin = localStorage.getItem('sc_admin')
        if (!isAdmin) {
            router.push('/admin/login')
            return
        }
        fetchUsers()
    }, [offset])

    const fetchUsers = async () => {
        try {
            const token = localStorage.getItem(config.authTokenKey)
            console.log('Fetching users - Token exists:', !!token)
            console.log('Token value:', token ? token.substring(0, 50) + '...' : 'none')
            console.log('API URL:', `${config.apiBaseUrl}/api/admin/users?limit=${limit}&offset=${offset}`)

            if (!token) {
                console.error('No token found, redirecting to login')
                router.push('/admin/login')
                return
            }

            const res = await fetch(`${config.apiBaseUrl}/api/admin/users?limit=${limit}&offset=${offset}`, {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            })

            console.log('Response status:', res.status)

            if (res.ok) {
                const data = await res.json()
                console.log('Users data:', data)
                setUsers(prev => offset === 0 ? data : [...prev, ...data])
                setHasMore(data.length === limit)
            } else {
                const error = await res.json()
                console.error('API Error:', error)

                if (res.status === 401) {
                    console.error('Token invalid or expired. Logging out.')
                    localStorage.removeItem(config.authTokenKey)
                    localStorage.removeItem(config.authUserKey)
                    localStorage.removeItem('sc_admin')
                    router.push('/admin/login')
                }
            }
        } catch (error) {
            console.error('Failed to fetch users:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleLoadMore = () => {
        setOffset(prev => prev + limit)
    }

    const handleUserUpdated = () => {
        // Refresh users list
        setOffset(0)
        setUsers([])
        fetchUsers()
    }

    return (
        <AdminSidebar>
            {/* Header */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 24,
            }}>
                <div>
                    <h1 style={{
                        margin: 0,
                        fontSize: 24,
                        fontWeight: 800,
                        color: T.navy,
                        letterSpacing: '-0.5px',
                    }}>
                        User Management
                    </h1>
                    <p style={{
                        margin: '6px 0 0',
                        fontSize: 13,
                        color: T.textMuted,
                    }}>
                        {users.length} users found · Manage user accounts and permissions
                    </p>
                </div>
            </div>

            {/* Filters (placeholder) */}
            <div style={{
                display: 'flex',
                gap: 12,
                marginBottom: 20,
            }}>
                <input
                    type="text"
                    placeholder="🔍 Search users..."
                    style={{
                        flex: 1,
                        padding: '10px 14px',
                        border: `1px solid ${T.border}`,
                        borderRadius: 10,
                        fontSize: 13,
                        outline: 'none',
                        fontFamily: "'DM Sans', sans-serif",
                    }}
                />
                <select
                    style={{
                        padding: '10px 14px',
                        border: `1px solid ${T.border}`,
                        borderRadius: 10,
                        fontSize: 13,
                        outline: 'none',
                        background: '#fff',
                        cursor: 'pointer',
                    }}
                >
                    <option value="all">All Roles</option>
                    <option value="admin">Admin</option>
                    <option value="user">User</option>
                </select>
                <select
                    style={{
                        padding: '10px 14px',
                        border: `1px solid ${T.border}`,
                        borderRadius: 10,
                        fontSize: 13,
                        outline: 'none',
                        background: '#fff',
                        cursor: 'pointer',
                    }}
                >
                    <option value="all">All Status</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                </select>
            </div>

            {/* User Table */}
            {loading && users.length === 0 ? (
                <div style={{
                    padding: 60,
                    textAlign: 'center',
                    color: T.textMuted,
                }}>
                    <span style={{ fontSize: 32, display: 'block', marginBottom: 16 }}>⏳</span>
                    Loading users...
                </div>
            ) : (
                <>
                    <UserTable
                        users={users}
                        onLoadMore={handleLoadMore}
                        onUserUpdated={handleUserUpdated}
                    />

                    {hasMore && (
                        <div style={{ marginTop: 16, textAlign: 'center' }}>
                            <button
                                onClick={handleLoadMore}
                                style={{
                                    padding: '10px 24px',
                                    background: T.blue,
                                    color: '#fff',
                                    border: 'none',
                                    borderRadius: 10,
                                    fontSize: 13,
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                }}
                            >
                                Load More
                            </button>
                        </div>
                    )}
                </>
            )}
        </AdminSidebar>
    )
}
