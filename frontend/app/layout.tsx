import type { Metadata, Viewport } from 'next'
import { Suspense } from 'react'
import './globals.css'
import ConditionalSidebar from '@/components/ConditionalSidebar'
import { PWAInstallPrompt } from '@/components/PWAInstallPrompt'

export const metadata: Metadata = {
    title: 'Zenalys — No-Code Platform for Traders',
    description: 'Build, backtest and deploy no-code trading strategies.',
    manifest: '/manifest.json',
    appleWebApp: {
        capable: true,
        statusBarStyle: 'black-translucent',
        title: 'SignalCraft',
    },
    formatDetection: {
        telephone: false,
    },
    themeColor: '#10B981',
}

export const viewport: Viewport = {
    themeColor: '#10B981',
    width: 'device-width',
    initialScale: 1,
    maximumScale: 1,
    userScalable: false,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#F8FAFC' }}>
                <Suspense fallback={null}>
                    <ConditionalSidebar />
                </Suspense>
                <main style={{ flex: 1, overflow: 'auto' }}>{children}</main>
                <PWAInstallPrompt />
            </body>
        </html>
    )
}
