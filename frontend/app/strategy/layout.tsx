import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Strategy Builder',
    description: 'Build your trading strategy.',
}

export default function StrategyLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
