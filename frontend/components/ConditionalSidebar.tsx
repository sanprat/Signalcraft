'use client'

import { usePathname } from 'next/navigation'
import Sidebar from './Sidebar'

// Pages that don't show the sidebar
const PUBLIC_PATHS = ['/', '/login']

export default function ConditionalSidebar() {
    const pathname = usePathname()
    if (PUBLIC_PATHS.includes(pathname) || pathname?.startsWith('/admin')) return null
    return <Sidebar />
}
