import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Admin',
    description: 'Admin dashboard.',
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
