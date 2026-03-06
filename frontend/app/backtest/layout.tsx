import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Backtest',
    description: 'Backtest your trading strategies.',
}

export default function BacktestLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
