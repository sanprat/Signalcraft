'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

const T = {
    navy: '#0F2744',
    blue: '#1D4ED8',
    blueLight: '#EFF6FF',
    border: '#E2E8F0',
    textMuted: '#94A3B8',
    text: '#0F172A',
}

interface BackButtonProps {
    defaultBack?: string
    className?: string
}

export function BackButton({ defaultBack = '/dashboard', className = '' }: BackButtonProps) {
    const router = useRouter()
    const [canGoBack, setCanGoBack] = useState(false)
    const [backUrl, setBackUrl] = useState(defaultBack)

    useEffect(() => {
        // Check if there's history to go back to
        setCanGoBack(window.history.length > 1)
        
        // Determine smart back URL based on current path
        const currentPath = window.location.pathname
        if (currentPath.includes('/strategy/')) {
            setBackUrl('/dashboard')
        } else if (currentPath.includes('/backtest/')) {
            setBackUrl('/backtest')
        } else if (currentPath.includes('/live')) {
            setBackUrl('/dashboard')
        } else if (currentPath.includes('/settings')) {
            setBackUrl('/dashboard')
        } else if (currentPath.includes('/chart/')) {
            setBackUrl('/dashboard')
        }
    }, [defaultBack])

    const handleBack = () => {
        if (canGoBack && window.history.length > 1) {
            router.back()
        } else {
            router.push(backUrl)
        }
    }

    return (
        <button
            onClick={handleBack}
            className={className}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 12px',
                background: T.blueLight,
                border: `1px solid ${T.border}`,
                borderRadius: 8,
                color: T.blue,
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s',
                minWidth: 'fit-content',
            }}
            onMouseEnter={(e) => {
                e.currentTarget.style.background = T.blue
                e.currentTarget.style.color = '#fff'
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.background = T.blueLight
                e.currentTarget.style.color = T.blue
            }}
        >
            <span style={{ fontSize: 16 }}>←</span>
            <span>Back</span>
        </button>
    )
}
