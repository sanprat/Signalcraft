import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Settings',
    description: 'Manage your account settings.',
}

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
