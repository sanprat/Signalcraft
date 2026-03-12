import type { Metadata, Viewport } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Dashboard',
    description: 'Your trading dashboard.',
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

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
