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
    // Check if already installed
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true)
      return
    }

    // Only show install prompt on login and dashboard pages
    if (pathname !== '/login' && pathname !== '/dashboard' && !pathname.startsWith('/dashboard')) {
      return
    }

    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)

      // Check if user hasn't dismissed before
      const dismissed = localStorage.getItem('pwa-install-dismissed')
      const dismissedAt = dismissed ? parseInt(dismissed) : 0
      const sevenDays = 7 * 24 * 60 * 60 * 1000
      
      if (Date.now() - dismissedAt > sevenDays) {
        setShowPrompt(true)
      }
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    }
  }, [pathname])

  const handleInstall = async () => {
    if (!deferredPrompt) return

    deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice

    if (outcome === 'accepted') {
      console.log('User accepted the install prompt')
      setIsInstalled(true)
    }

    setDeferredPrompt(null)
    setShowPrompt(false)
  }

  const handleDismiss = () => {
    setShowPrompt(false)
    localStorage.setItem('pwa-install-dismissed', Date.now().toString())
  }

  if (!showPrompt || isInstalled) return null

  return (
    <div style={{
      position: 'fixed',
      bottom: 20,
      left: '50%',
      transform: 'translateX(-50%)',
      background: 'linear-gradient(135deg, #10B981, #047857)',
      color: '#fff',
      padding: '16px 20px',
      borderRadius: 16,
      boxShadow: '0 10px 40px rgba(16, 185, 129, 0.4)',
      zIndex: 10000,
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      maxWidth: '95%',
      width: 380,
      animation: 'slideUp 0.3s ease-out',
    }}>
      <div style={{
        width: 44,
        height: 44,
        background: 'rgba(255,255,255,0.2)',
        borderRadius: 12,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 22,
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
            padding: '8px 12px',
            background: 'rgba(255,255,255,0.15)',
            border: 'none',
            borderRadius: 8,
            color: '#fff',
            fontWeight: 600,
            cursor: 'pointer',
            fontSize: 12,
          }}
        >
          Later
        </button>
        <button
          onClick={handleInstall}
          style={{
            padding: '8px 14px',
            background: '#fff',
            border: 'none',
            borderRadius: 8,
            color: '#047857',
            fontWeight: 700,
            cursor: 'pointer',
            fontSize: 12,
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
        
        @media (max-width: 480px) {
          .pwa-prompt {
            width: 95% !important;
            padding: 12px 16px !important;
          }
        }
      `}</style>
    </div>
  )
}
