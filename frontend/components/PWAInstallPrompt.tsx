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
  const [showHowTo, setShowHowTo] = useState(false)
  const [isInstalled, setIsInstalled] = useState(false)
  const [swReady, setSwReady] = useState(false)

  useEffect(() => {
    const checkPWAStatus = async () => {
      if (typeof window === 'undefined') return

      if (window.matchMedia('(display-mode: standalone)').matches) {
        console.log('[PWA] Running in standalone mode - already installed')
        setIsInstalled(true)
        return
      }

      if (window.matchMedia('(display-mode: minimal-ui)').matches) {
        console.log('[PWA] Running in minimal-ui mode')
        setIsInstalled(true)
        return
      }

      if ((navigator as any).standalone === true) {
        console.log('[PWA] navigator.standalone is true - already installed')
        setIsInstalled(true)
        return
      }

      try {
        const registration = await navigator.serviceWorker?.getRegistration('/sw.js')
        if (registration) {
          console.log('[PWA] Service worker registered:', registration.scope)
          setSwReady(true)
        } else {
          console.log('[PWA] No service worker registration found')
        }
      } catch (err) {
        console.log('[PWA] Service worker check failed:', err)
      }
    }

    checkPWAStatus()

    const isSecure = window.location.protocol === 'https:' || 
                     window.location.hostname === 'localhost' ||
                     window.location.hostname === '127.0.0.1'
    
    if (!isSecure) {
      const protocol = window.location.protocol
      const hostname = window.location.hostname
      console.log(`[PWA] Not secure: protocol=${protocol}, hostname=${hostname}`)
    }

    if (pathname !== '/login' && pathname !== '/dashboard' && !pathname.startsWith('/dashboard')) {
      return
    }

    const dismissed = localStorage.getItem('pwa-install-dismissed')
    const dismissedAt = dismissed ? parseInt(dismissed) : 0
    const sevenDays = 7 * 24 * 60 * 60 * 1000
    
    if (dismissed && Date.now() - dismissedAt <= sevenDays) {
      console.log('[PWA] Prompt dismissed recently, not showing')
      return
    }

    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault()
      console.log('[PWA] beforeinstallprompt event fired')
      setDeferredPrompt(e as BeforeInstallPromptEvent)
      setShowPrompt(true)
    }

    const handleAppInstalled = () => {
      console.log('[PWA] App installed!')
      setIsInstalled(true)
      setShowPrompt(false)
    }

    const checkPromptAvailability = () => {
      const hasPrompt = deferredPrompt !== null
      if (!hasPrompt) {
        const visitCount = parseInt(localStorage.getItem('pwa-visit-count') || '0') + 1
        localStorage.setItem('pwa-visit-count', visitCount.toString())
        console.log(`[PWA] Visit count: ${visitCount}`)
        
        if (visitCount >= 1) {
          console.log('[PWA] Showing prompt fallback after visits')
          setShowPrompt(true)
        }
      }
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleAppInstalled)

    setTimeout(checkPromptAvailability, 2000)

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      window.removeEventListener('appinstalled', handleAppInstalled)
    }
  }, [pathname])

  const handleInstall = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    
    if (deferredPrompt) {
      try {
        deferredPrompt.prompt()
        const { outcome } = await deferredPrompt.userChoice

        if (outcome === 'accepted') {
          console.log('[PWA] User accepted the install prompt')
          setIsInstalled(true)
        }
      } catch (error) {
        console.error('[PWA] Error showing prompt:', error)
      } finally {
        setDeferredPrompt(null)
        setShowPrompt(false)
      }
      return
    }

    setShowHowTo(true)
  }

  const handleDismiss = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setShowPrompt(false)
    setShowHowTo(false)
    localStorage.setItem('pwa-install-dismissed', Date.now().toString())
  }

  const closeHowTo = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setShowHowTo(false)
  }

  if (isInstalled) return null

  if (!showPrompt) return null

  return (
    <>
      <div className="pwa-prompt" style={{
        position: 'fixed',
        bottom: 80,
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
        width: 380,
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
            {deferredPrompt ? 'Tap Install to add to home screen' : 'Tap menu → Add to Home Screen'}
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
            {deferredPrompt ? 'Install' : 'How to'}
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

      {showHowTo && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          zIndex: 10001,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 20,
        }} onClick={closeHowTo}>
          <div style={{
            background: '#fff',
            borderRadius: 20,
            padding: 24,
            maxWidth: 400,
            width: '100%',
            color: '#1a1a1a',
          }} onClick={e => e.stopPropagation()}>
            <div style={{ 
              fontSize: 20, 
              fontWeight: 700, 
              marginBottom: 16,
              textAlign: 'center'
            }}>
              📲 Add to Home Screen
            </div>
            
            <div style={{ fontSize: 14, lineHeight: 1.6, color: '#4a4a4a' }}>
              <p style={{ marginBottom: 16 }}>
                <strong>To install SignalCraft as an app:</strong>
              </p>
              
              <div style={{ 
                background: '#f5f5f5', 
                borderRadius: 12, 
                padding: 16,
                marginBottom: 16 
              }}>
                <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                  <span style={{ 
                    width: 28, height: 28, 
                    background: '#10B981', color: '#fff',
                    borderRadius: '50%', 
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: 14, flexShrink: 0
                  }}>1</span>
                  <span>Tap the <strong>⋮</strong> (three dots) or <strong>menu</strong> button in your browser</span>
                </div>
                <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                  <span style={{ 
                    width: 28, height: 28, 
                    background: '#10B981', color: '#fff',
                    borderRadius: '50%', 
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: 14, flexShrink: 0
                  }}>2</span>
                  <span>Select <strong>"Add to Home Screen"</strong> or <strong>"Install App"</strong></span>
                </div>
                <div style={{ display: 'flex', gap: 12 }}>
                  <span style={{ 
                    width: 28, height: 28, 
                    background: '#10B981', color: '#fff',
                    borderRadius: '50%', 
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: 14, flexShrink: 0
                  }}>3</span>
                  <span>Tap <strong>Add</strong> to confirm</span>
                </div>
              </div>
              
              <p style={{ fontSize: 12, color: '#666', textAlign: 'center' }}>
                The app will appear on your home screen like a native app
              </p>
            </div>
            
            <button
              onClick={closeHowTo}
              style={{
                width: '100%',
                marginTop: 16,
                padding: '12px 24px',
                background: '#10B981',
                border: 'none',
                borderRadius: 10,
                color: '#fff',
                fontWeight: 600,
                fontSize: 15,
                cursor: 'pointer',
              }}
            >
              Got it!
            </button>
          </div>
        </div>
      )}
    </>
  )
}
