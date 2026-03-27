'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { getSymbols } from '@/lib/api/strategy'

interface UseSymbolsReturn {
    symbols: string[]
    filteredSymbols: string[]
    searchQuery: string
    setSearchQuery: (query: string) => void
    isLoading: boolean
    error: string | null
    refresh: () => Promise<void>
}

export function useSymbols(): UseSymbolsReturn {
    const [symbols, setSymbols] = useState<string[]>([])
    const [searchQuery, setSearchQuery] = useState('')
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchSymbols = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            const result = await getSymbols()
            setSymbols(result)
        } catch (err) {
            console.error('Failed to fetch symbols:', err)
            setError('Failed to load symbols')
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchSymbols()
    }, [fetchSymbols])

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
