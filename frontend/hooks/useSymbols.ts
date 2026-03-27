'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { getSymbols as fetchSymbolsFromApi } from '@/lib/api/strategy'

interface UseSymbolsReturn {
    symbols: string[]
    filteredSymbols: string[]
    searchQuery: string
    setSearchQuery: (query: string) => void
    isLoading: boolean
    error: string | null
    refresh: () => Promise<void>
}

const SYMBOLS_CACHE_KEY = 'nifty500_symbols'
const SYMBOLS_CACHE_TTL = 24 * 60 * 60 * 1000 // 24 hours

function getCachedSymbols(): string[] | null {
    if (typeof window === 'undefined') return null
    try {
        const cached = localStorage.getItem(SYMBOLS_CACHE_KEY)
        if (!cached) return null
        const { symbols, timestamp } = JSON.parse(cached)
        // Check if cache is still valid (within 24 hours)
        if (Date.now() - timestamp < SYMBOLS_CACHE_TTL) {
            return symbols
        }
        return null
    } catch {
        return null
    }
}

function setCachedSymbols(symbols: string[]): void {
    if (typeof window === 'undefined') return
    try {
        localStorage.setItem(SYMBOLS_CACHE_KEY, JSON.stringify({
            symbols,
            timestamp: Date.now(),
        }))
    } catch {
        // Ignore localStorage errors
    }
}

export function useSymbols(): UseSymbolsReturn {
    // Initialize from localStorage cache if available
    const [symbols, setSymbols] = useState<string[]>(() => {
        const cached = getCachedSymbols()
        return cached || []
    })
    const [searchQuery, setSearchQuery] = useState('')
    const [isLoading, setIsLoading] = useState(symbols.length === 0)
    const [error, setError] = useState<string | null>(null)

    const fetchSymbols = useCallback(async () => {
        // Skip fetch if we have cached symbols
        const cached = getCachedSymbols()
        if (cached && cached.length > 0) {
            setSymbols(cached)
            setIsLoading(false)
            return
        }

        setIsLoading(true)
        setError(null)
        try {
            const result = await fetchSymbolsFromApi()
            if (result.length > 0) {
                setSymbols(result)
                setCachedSymbols(result)
            }
        } catch (err) {
            console.error('Failed to fetch symbols:', err)
            setError('Failed to load symbols')
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        if (symbols.length === 0) {
            fetchSymbols()
        }
    }, [fetchSymbols, symbols.length])

    const filteredSymbols = useMemo(() => {
        if (!searchQuery.trim()) return symbols
        const query = searchQuery.toLowerCase()
        return symbols.filter(s => s.toLowerCase().includes(query))
    }, [symbols, searchQuery])

    return {
        symbols,
        filteredSymbols,
        searchQuery,
        setSearchQuery,
        isLoading,
        error,
        refresh: fetchSymbols,
    }
}
