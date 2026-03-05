'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { AdminSidebar } from '@/components/admin/AdminSidebar'

const T = {
    navy: '#0F2744',
    surface: '#FFFFFF',
    border: '#E2E8F0',
    textMuted: '#94A3B8',
}

export default function AdminStrategiesPage() {
    const router = useRouter()

    useEffect(() => {
        const isAdmin = localStorage.getItem('sc_admin')
        if (!isAdmin) {
            router.push('/admin/login')
            return
        }
    }, [])

    return (
        <AdminSidebar>
            <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '60vh',
                color: T.textMuted,
            }}>
                <span style={{ fontSize: 64, marginBottom: 24 }}>⚡</span>
                <h1 style={{
                    margin: 0,
                    fontSize: 20,
                    fontWeight: 700,
                    color: T.navy,
                }}>
                    Strategy Management
                </h1>
                <p style={{
                    margin: '8px 0 0',
                    fontSize: 14,
                }}>
                    Coming soon · This feature is under development
                </p>
            </div>
        </AdminSidebar>
    )
}
