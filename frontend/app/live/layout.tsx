import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Live Trading',
    description: 'Monitor your live trading strategies.',
}

export default function LiveLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
