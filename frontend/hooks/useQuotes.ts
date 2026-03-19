'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { config } from '@/lib/config'

export type QuoteData = { ltp: number; chg: number; up: boolean }
export type Quotes = Record<string, QuoteData>

const logger = {
    warn: (...args: any[]) => console.warn("[useQuotes]", ...args),
    error: (...args: any[]) => console.error("[useQuotes]", ...args)
};

const INITIAL_QUOTES: Quotes = {
    'NIFTY 50': { ltp: 0.0, chg: 0.0, up: true },
    'BANKNIFTY': { ltp: 0.0, chg: 0.0, up: true },
    'FINNIFTY': { ltp: 0.0, chg: 0.0, up: true },
    'SENSEX': { ltp: 0.0, chg: 0.0, up: true },
}

export function useQuotes(apiBase = config.apiBaseUrl) {
    const [isMounted, setIsMounted] = useState(false)
    const [quotes, setQuotes] = useState<Quotes>(INITIAL_QUOTES)
    const [connected, setConnected] = useState(false)
    const [isLive, setIsLive] = useState(false)
    const [marketOpen, setMarketOpen] = useState(false)
    const [lastUpdate, setLastUpdate] = useState<string>('')
    const wsRef = useRef<WebSocket | null>(null)
    const pendingSubscriptionsRef = useRef<Set<string>>(new Set());

    useEffect(() => {
        setIsMounted(true)
        let retryTimer: ReturnType<typeof setTimeout>
        let dead = false

        const connect = () => {
            if (dead) return
            let wsUrl: string
            if (apiBase) {
                wsUrl = `${apiBase.replace('http', 'ws')}/ws/quotes`
            } else {
                const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
                wsUrl = `${proto}//${window.location.host}/ws/quotes`
            }
            const ws = new WebSocket(wsUrl)
            wsRef.current = ws

            ws.onopen = () => {
                setConnected(true)
                // Flush pending subscriptions
                pendingSubscriptionsRef.current.forEach(symbol => {
                    ws.send(JSON.stringify({ type: 'subscribe', symbol }));
                });
                pendingSubscriptionsRef.current.clear();
            }

            ws.onmessage = (e) => {
                try {
                    const msg = JSON.parse(e.data)
                    if (msg.type === 'quotes' && msg.data) {
                        setQuotes(msg.data)
                        setIsLive(!!msg.live)
                        setMarketOpen(!!msg.market_open)
                        setLastUpdate(msg.ts || '')
                    }
                } catch { }
            }

            ws.onclose = () => {
                setConnected(false)
                // Auto-reconnect after 3s
                if (!dead) retryTimer = setTimeout(connect, 3000)
            }

            ws.onerror = () => ws.close()
        }

        // Also try REST as initial data if WS is slow to connect
        fetch(`${apiBase}/api/quotes`)
            .then(r => r.json())
            .then(d => { if (d.quotes) setQuotes(d.quotes) })
            .catch(() => { })

        connect()

        return () => {
            dead = true
            clearTimeout(retryTimer)
            wsRef.current?.close()
        }
    }, [apiBase])

    const subscribe = useCallback((symbol: string) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'subscribe', symbol }));
        } else {
            // Queue the subscription if WS is not open
            pendingSubscriptionsRef.current.add(symbol);
            logger.warn("WebSocket not open, queuing subscription for", symbol);
        }
    }, []); // No dependencies needed as it uses refs

    return isMounted ? {
        quotes,
        connected,
        isLive,
        marketOpen,
        lastUpdate,
        subscribe
    } : {
        quotes: INITIAL_QUOTES,
        connected: false,
        isLive: false,
        marketOpen: false,
        lastUpdate: '',
        subscribe: () => { }
    }
}
