import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Craft Your Trading Signals',
    description: 'Build, backtest and deploy no-code trading strategies.',
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
