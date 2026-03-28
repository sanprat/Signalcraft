import type { Metadata, Viewport } from 'next'
import { Suspense } from 'react'
import './globals.css'
import TopNavbar from '@/components/TopNavbar'

export const metadata: Metadata = {
    title: 'Zenalys — No-Code Platform for Traders',
    description: 'Build, backtest and deploy no-code trading strategies.',
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
            <body style={{ 
                display: 'flex', 
                flexDirection: 'column',
                height: '100vh', 
                overflow: 'hidden', 
                background: '#F8FAFC' 
            }}>
                <Suspense fallback={null}>
                    <TopNavbar />
                </Suspense>
                <main style={{ flex: 1, overflow: 'auto' }}>{children}</main>
            </body>
        </html>
    )
}
