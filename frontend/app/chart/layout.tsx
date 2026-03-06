import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'SignalCraft — Chart',
    description: 'Interactive trading charts.',
}

export default function ChartLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>
}
