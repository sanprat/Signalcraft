'use client'

import { useState, useEffect } from 'react'

export default function PWADebugPage() {
  const [manifest, setManifest] = useState<any>(null)
  const [serviceWorker, setServiceWorker] = useState<any>(null)
  const [installPrompt, setInstallPrompt] = useState<any>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [checks, setChecks] = useState<{name: string, pass: boolean, message: string}[]>([])

  useEffect(() => {
    runDiagnostics()
  }, [])

  const runDiagnostics = async () => {
    const newChecks: {name: string, pass: boolean, message: string}[] = []
    const newErrors: string[] = []

    // 1. Check manifest
    try {
      const response = await fetch('/manifest.json')
      const data = await response.json()
      setManifest(data)
      newChecks.push({
        name: 'Manifest',
        pass: true,
        message: '✅ Manifest loaded successfully'
      })
    } catch (err: any) {
      newErrors.push(`Failed to load manifest: ${err.message}`)
      newChecks.push({
        name: 'Manifest',
        pass: false,
        message: '❌ Failed to load manifest'
      })
    }

    // 2. Check service worker
    if ('serviceWorker' in navigator) {
      const registration = await navigator.serviceWorker.getRegistration()
      if (registration) {
        setServiceWorker({
          registered: true,
          active: registration.active?.state,
          waiting: registration.waiting?.state,
          installing: registration.installing?.state
        })
        newChecks.push({
          name: 'Service Worker',
          pass: true,
          message: `✅ Service Worker registered (state: ${registration.active?.state || 'activating'})`
        })
      } else {
        newErrors.push('Service Worker not registered')
        newChecks.push({
          name: 'Service Worker',
          pass: false,
          message: '❌ Service Worker not registered'
        })
      }
    } else {
      newErrors.push('Service Workers not supported')
      newChecks.push({
        name: 'Service Worker',
        pass: false,
        message: '❌ Service Workers not supported in this browser'
      })
    }

    // 3. Check install prompt
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault()
      setInstallPrompt({ available: true })
      newChecks.push({
        name: 'Install Prompt',
        pass: true,
        message: '✅ Install prompt available'
      })
      setChecks([...newChecks, {
        name: 'Install Prompt',
        pass: true,
        message: '✅ Install prompt available'
      }])
    })

    // 4. Check if already installed
    if (window.matchMedia('(display-mode: standalone)').matches) {
      newChecks.push({
        name: 'PWA Mode',
        pass: true,
        message: '✅ Running as installed PWA'
      })
    } else {
      newChecks.push({
        name: 'PWA Mode',
        pass: false,
        message: 'ℹ️ Running in browser (not installed)'
      })
    }

    // 5. Check icons
    if (manifest?.icons) {
      const iconChecks = await Promise.all(
        manifest.icons.map(async (icon: any) => {
          try {
            const response = await fetch(icon.src)
            return response.ok
          } catch {
            return false
          }
        })
      )
      const allIconsLoad = iconChecks.every((loaded: boolean) => loaded)
      if (allIconsLoad) {
        newChecks.push({
          name: 'Icons',
          pass: true,
          message: `✅ All ${manifest.icons.length} icons load correctly`
        })
      } else {
        newErrors.push('Some icons failed to load')
        newChecks.push({
          name: 'Icons',
          pass: false,
          message: '❌ Some icons failed to load'
        })
      }
    }

    // 6. Check HTTPS
    if (window.location.protocol === 'https:' || window.location.hostname === 'localhost') {
      newChecks.push({
        name: 'HTTPS',
        pass: true,
        message: '✅ Served over secure connection'
      })
    } else {
      newErrors.push('Not served over HTTPS')
      newChecks.push({
        name: 'HTTPS',
        pass: false,
        message: '❌ Not served over HTTPS (required for PWA)'
      })
    }

    setChecks(newChecks)
    setErrors(newErrors)
  }

  const handleInstall = async () => {
    if (installPrompt) {
      // In real implementation, you'd have the deferred prompt event
      alert('Install prompt available! Tap the browser menu (⋮) → "Install app"')
    } else {
      alert('Install prompt not available yet. Wait a few seconds or refresh the page.')
    }
  }

  return (
    <div style={{ padding: 24, fontFamily: "'DM Sans', sans-serif", maxWidth: 800, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 24 }}>PWA Diagnostics</h1>

      {/* Run Diagnostics Button */}
      <button
        onClick={runDiagnostics}
        style={{
          padding: '12px 24px',
          background: '#1D4ED8',
          color: '#fff',
          border: 'none',
          borderRadius: 8,
          fontSize: 14,
          fontWeight: 700,
          cursor: 'pointer',
          marginBottom: 24
        }}
      >
        🔄 Run Diagnostics
      </button>

      {/* Install Button */}
      {installPrompt?.available && (
        <button
          onClick={handleInstall}
          style={{
            padding: '12px 24px',
            background: '#059669',
            color: '#fff',
            border: 'none',
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 700,
            cursor: 'pointer',
            marginLeft: 12
          }}
        >
          📲 Install App
        </button>
      )}

      {/* Checks */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>Diagnostics</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {checks.map((check, i) => (
            <div
              key={i}
              style={{
                padding: '12px 16px',
                background: check.pass ? '#ECFDF5' : check.name === 'PWA Mode' ? '#EFF6FF' : '#FEF2F2',
                border: `1px solid ${check.pass ? '#059669' : '#DC2626'}`,
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 600,
                color: check.pass ? '#059669' : '#DC2626'
              }}
            >
              {check.message}
            </div>
          ))}
        </div>
      </div>

      {/* Errors */}
      {errors.length > 0 && (
        <div style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>Errors</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {errors.map((error, i) => (
              <div
                key={i}
                style={{
                  padding: '12px 16px',
                  background: '#FEF2F2',
                  border: '1px solid #FECACA',
                  borderRadius: 8,
                  fontSize: 13,
                  color: '#DC2626'
                }}
              >
                {error}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Manifest Info */}
      {manifest && (
        <div style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>Manifest Info</h2>
          <pre style={{
            background: '#F8FAFC',
            padding: 16,
            borderRadius: 8,
            fontSize: 12,
            fontFamily: "'DM Mono', monospace",
            overflow: 'auto'
          }}>
            {JSON.stringify(manifest, null, 2)}
          </pre>
        </div>
      )}

      {/* Service Worker Info */}
      {serviceWorker && (
        <div style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>Service Worker</h2>
          <pre style={{
            background: '#F8FAFC',
            padding: 16,
            borderRadius: 8,
            fontSize: 12,
            fontFamily: "'DM Mono', monospace",
            overflow: 'auto'
          }}>
            {JSON.stringify(serviceWorker, null, 2)}
          </pre>
        </div>
      )}

      {/* Manual Install Instructions */}
      <div style={{
        padding: 16,
        background: '#EFF6FF',
        border: '1px solid #BFDBFE',
        borderRadius: 8,
        fontSize: 13
      }}>
        <strong>💡 Manual Install Steps:</strong>
        <ol style={{ marginTop: 8, marginLeft: 20 }}>
          <li>Tap the browser menu (⋮ three dots)</li>
          <li>Look for "Install app" or "Add to Home screen"</li>
          <li>Tap "Install" or "Add"</li>
          <li>App will appear on your home screen</li>
        </ol>
      </div>
    </div>
  )
}
