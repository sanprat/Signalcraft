import type { Metadata, Viewport } from 'next'
import { Suspense } from 'react'
import './globals.css'
import { PWAInstallPrompt } from '@/components/PWAInstallPrompt'
import ConditionalSidebar from '@/components/ConditionalSidebar'

export const metadata: Metadata = {
    title: 'Zenalys — No-Code Platform for Traders',
    description: 'Build, backtest and deploy no-code trading strategies.',
    manifest: '/manifest.json',
    appleWebApp: {
        capable: true,
        statusBarStyle: 'black-translucent',
        title: 'SignalCraft',
    },
    other: {
        'mobile-web-app-capable': 'yes',
        'apple-mobile-web-app-status-bar-style': 'black-translucent',
        'apple-mobile-web-app-title': 'SignalCraft',
    },
    formatDetection: {
        telephone: false,
    },
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
            <head>
                <link rel="manifest" href="/manifest.json" />
                <meta name="theme-color" content="#10B981" />
                <meta name="apple-mobile-web-app-capable" content="yes" />
                <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
                <meta name="apple-mobile-web-app-title" content="SignalCraft" />
            </head>
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
