/**
 * SignalCraft Frontend Configuration
 * In production (behind Nginx), API calls use relative URLs (empty base).
 * In development (localhost), API calls go to localhost:8001.
 */

function getApiBaseUrl(): string {
  // If env var is explicitly set, use it
  const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL
  if (envUrl) return envUrl

  // In browser: auto-detect based on hostname
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'http://localhost:8001' // Local dev
    }
    return '' // Production — use relative URLs through Nginx
  }

  // Server-side rendering — use empty (relative)
  return ''
}

export const config = {
  // API Configuration
  apiBaseUrl: getApiBaseUrl(),

  // App Configuration
  appName: process.env.NEXT_PUBLIC_APP_NAME || 'SignalCraft',
  appTagline: process.env.NEXT_PUBLIC_APP_TAGLINE || 'Visual no-code strategy builder. Build, backtest, and execute strategies for Options (NIFTY, BANKNIFTY, FINNIFTY) and Stocks (Nifty 500) — all in one platform.',

  // Auth Configuration
  authTokenKey: process.env.NEXT_PUBLIC_AUTH_TOKEN_KEY || 'sc_token',
  authUserKey: process.env.NEXT_PUBLIC_AUTH_USER_KEY || 'sc_user',
  tokenMaxAgeDays: parseInt(process.env.NEXT_PUBLIC_TOKEN_MAX_AGE_DAYS || '7'),

  // Feature Flags
  enableMockData: process.env.NEXT_PUBLIC_ENABLE_MOCK_DATA === 'true',

  // Market Configuration
  marketOpenHour: 9,
  marketOpenMinute: 15,
  marketCloseHour: 15,
  marketCloseMinute: 30,
} as const

export type Config = typeof config
