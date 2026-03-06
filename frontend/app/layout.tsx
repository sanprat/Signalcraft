import type { Metadata } from 'next'
import { Suspense } from 'react'
import './globals.css'
import ConditionalSidebar from '@/components/ConditionalSidebar'

export const metadata: Metadata = {
    title: 'Zenalys — No-Code AI Platform for Traders',
    description: 'Build, backtest and deploy no-code trading strategies with AI-powered insights.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#F8FAFC' }}>
                <Suspense fallback={null}>
                    <ConditionalSidebar />
                </Suspense>
                <main style={{ flex: 1, overflow: 'auto' }}>{children}</main>
            </body>
        </html>
    )
}
