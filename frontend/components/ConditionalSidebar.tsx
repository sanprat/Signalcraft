'use client'

import { useState, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import Sidebar from './Sidebar'

// Pages that don't show the sidebar
const PUBLIC_PATHS = ['/', '/login']

export default function ConditionalSidebar() {
    const pathname = usePathname()
    const [isMobile, setIsMobile] = useState(false)

    useEffect(() => {
        const checkMobile = () => {
            setIsMobile(window.innerWidth < 768)
        }
        
        // Initial check
        checkMobile()
        
        // Listen for resize
        window.addEventListener('resize', checkMobile)
        return () => window.removeEventListener('resize', checkMobile)
    }, [])

    // Don't show desktop sidebar on mobile (use hamburger menu instead)
    if (isMobile) return null
    
    // Don't show on public pages
    if (PUBLIC_PATHS.includes(pathname) || pathname?.startsWith('/admin')) return null
    
    return <Sidebar />
}
