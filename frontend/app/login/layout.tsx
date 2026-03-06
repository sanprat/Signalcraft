import type { Metadata, Viewport } from 'next'
import { PWAInstallPrompt } from '@/components/PWAInstallPrompt'

export const metadata: Metadata = {
    title: 'SignalCraft — Craft Your Trading Signals',
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

export default function AppLayout({ children }: { children: React.ReactNode }) {
    return (
        <>
            {children}
            <PWAInstallPrompt />
        </>
    )
}
