'use client'

import { useState, useEffect } from 'react'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export function PWAInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [showPrompt, setShowPrompt] = useState(false)

  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)
      
      // Check if user hasn't dismissed before
      const dismissed = localStorage.getItem('pwa-install-dismissed')
      if (!dismissed) {
        setShowPrompt(true)
      }
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    
    // Auto-dismiss after 7 days
    const timer = setTimeout(() => {
      setShowPrompt(false)
    }, 7 * 24 * 60 * 60 * 1000)

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      clearTimeout(timer)
    }
  }, [])

  const handleInstall = async () => {
    if (!deferredPrompt) return

    deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice
    
    if (outcome === 'accepted') {
      console.log('User accepted the install prompt')
    }
    
    setDeferredPrompt(null)
    setShowPrompt(false)
  }

  const handleDismiss = () => {
    setShowPrompt(false)
    localStorage.setItem('pwa-install-dismissed', 'true')
  }

  if (!showPrompt) return null

  return (
    <div style={{
      position: 'fixed',
      bottom: 20,
      left: '50%',
      transform: 'translateX(-50%)',
      background: 'linear-gradient(135deg, #10B981, #047857)',
      color: '#fff',
      padding: '16px 24px',
      borderRadius: 16,
      boxShadow: '0 10px 40px rgba(16, 185, 129, 0.4)',
      zIndex: 1000,
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      maxWidth: '90%',
      width: 400,
      animation: 'slideUp 0.3s ease-out',
    }}>
      <div style={{
        width: 48,
        height: 48,
        background: 'rgba(255,255,255,0.2)',
        borderRadius: 12,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 24,
        fontWeight: 900,
        flexShrink: 0,
      }}>
        SC
      </div>
      
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>
          Install SignalCraft
        </div>
        <div style={{ fontSize: 13, opacity: 0.9, lineHeight: 1.4 }}>
          Add to home screen for quick access
        </div>
      </div>
      
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={handleDismiss}
          style={{
            padding: '8px 16px',
            background: 'rgba(255,255,255,0.2)',
            border: 'none',
            borderRadius: 8,
            color: '#fff',
            fontWeight: 600,
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Later
        </button>
        <button
          onClick={handleInstall}
          style={{
            padding: '8px 16px',
            background: '#fff',
            border: 'none',
            borderRadius: 8,
            color: '#047857',
            fontWeight: 700,
            cursor: 'pointer',
            fontSize: 13,
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
