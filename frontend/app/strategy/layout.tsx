import type { Metadata, Viewport } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Strategy Builder',
    description: 'Build your trading strategy.',
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

export default function StrategyLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
