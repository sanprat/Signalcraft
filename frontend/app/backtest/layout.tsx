import type { Metadata, Viewport } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Backtest',
    description: 'Backtest your trading strategies.',
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

export default function BacktestLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
