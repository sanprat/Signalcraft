'use client'

import { useState, useEffect } from 'react'
import { usePathname } from 'next/navigation'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export function PWAInstallPrompt() {
  const pathname = usePathname()
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [showPrompt, setShowPrompt] = useState(false)
  const [isInstalled, setIsInstalled] = useState(false)

  useEffect(() => {
    // Check if already installed (running in standalone mode)
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true)
      return
    }

    // Check if running on HTTPS or localhost (required for PWA)
    const isSecure = window.location.protocol === 'https:' || window.location.hostname === 'localhost'
    if (!isSecure) {
      console.log('[PWA] Not installing: requires HTTPS or localhost')
      return
    }

    // Only show install prompt on login and dashboard pages
    if (pathname !== '/login' && pathname !== '/dashboard' && !pathname.startsWith('/dashboard')) {
      return
    }

    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault()
      console.log('[PWA] beforeinstallprompt event fired')
      setDeferredPrompt(e as BeforeInstallPromptEvent)

      // Check if user hasn't dismissed before
      const dismissed = localStorage.getItem('pwa-install-dismissed')
      const dismissedAt = dismissed ? parseInt(dismissed) : 0
      const sevenDays = 7 * 24 * 60 * 60 * 1000
      
      // Show prompt if never dismissed or dismissed more than 7 days ago
      if (!dismissed || Date.now() - dismissedAt > sevenDays) {
        console.log('[PWA] Showing install prompt')
        setShowPrompt(true)
      } else {
        console.log('[PWA] Prompt dismissed recently, not showing')
      }
    }

    const handleAppInstalled = () => {
      console.log('[PWA] App installed!')
      setIsInstalled(true)
      setShowPrompt(false)
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleAppInstalled)

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      window.removeEventListener('appinstalled', handleAppInstalled)
    }
  }, [pathname])

  const handleInstall = async () => {
    if (!deferredPrompt) {
      console.log('[PWA] No install prompt available')
      return
    }

    try {
      deferredPrompt.prompt()
      const { outcome } = await deferredPrompt.userChoice

      if (outcome === 'accepted') {
        console.log('[PWA] User accepted the install prompt')
        setIsInstalled(true)
      } else {
        console.log('[PWA] User dismissed the install prompt')
      }
    } catch (error) {
      console.error('[PWA] Error showing prompt:', error)
    } finally {
      setDeferredPrompt(null)
      setShowPrompt(false)
    }
  }

  const handleDismiss = () => {
    setShowPrompt(false)
    localStorage.setItem('pwa-install-dismissed', Date.now().toString())
  }

  if (!showPrompt || isInstalled) return null

  return (
    <div className="pwa-prompt" style={{
      position: 'fixed',
      bottom: 80, // Above the mobile nav
      left: '50%',
      transform: 'translateX(-50%)',
      background: 'linear-gradient(135deg, #10B981, #047857)',
      color: '#fff',
      padding: '14px 18px',
      borderRadius: 16,
      boxShadow: '0 10px 40px rgba(16, 185, 129, 0.4)',
      zIndex: 10000,
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      maxWidth: '95%',
      width: 360,
      animation: 'slideUp 0.3s ease-out',
    }}>
      <div style={{
        width: 40,
        height: 40,
        background: 'rgba(255,255,255,0.2)',
        borderRadius: 10,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 20,
        fontWeight: 900,
        flexShrink: 0,
      }}>
        SC
      </div>

      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 3 }}>
          📲 Install SignalCraft
        </div>
        <div style={{ fontSize: 12, opacity: 0.95, lineHeight: 1.3 }}>
          Add to home screen for quick access
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6 }}>
        <button
          onClick={handleDismiss}
          style={{
            padding: '6px 10px',
            background: 'rgba(255,255,255,0.15)',
            border: 'none',
            borderRadius: 6,
            color: '#fff',
            fontWeight: 600,
            cursor: 'pointer',
            fontSize: 11,
          }}
        >
          Later
        </button>
        <button
          onClick={handleInstall}
          style={{
            padding: '6px 12px',
            background: '#fff',
            border: 'none',
            borderRadius: 6,
            color: '#047857',
            fontWeight: 700,
            cursor: 'pointer',
            fontSize: 11,
          }}
        >
          Install
        </button>
      </div>

      <style jsx>{`
        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateX(-50%) translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
          }
        }
      `}</style>
    </div>
  )
}
