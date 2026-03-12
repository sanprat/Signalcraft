import type { Metadata, Viewport } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Admin',
    description: 'Admin dashboard.',
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

export default function AdminLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
