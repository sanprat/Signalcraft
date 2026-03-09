import type { Metadata, Viewport } from 'next'
import { Suspense } from 'react'
import './globals.css'
import ConditionalSidebar from '@/components/ConditionalSidebar'

export const metadata: Metadata = {
    title: 'Zenalys — No-Code Platform for Traders',
    description: 'Build, backtest and deploy no-code trading strategies.',
    formatDetection: {
        telephone: false,
    },
}

export const viewport: Viewport = {
    themeColor: '#0F2744',
    width: 'device-width',
    initialScale: 1,
    maximumScale: 5,
    userScalable: true,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <head>
                <meta name="theme-color" content="#0F2744" />
            </head>
            <body style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#F8FAFC' }}>
                <Suspense fallback={null}>
                    <ConditionalSidebar />
                </Suspense>
                <main style={{ flex: 1, overflow: 'auto', WebkitOverflowScrolling: 'touch' }}>{children}</main>
            </body>
        </html>
    )
}
