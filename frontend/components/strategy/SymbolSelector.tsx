'use client'

import { useState, useMemo } from 'react'
import { useSymbols } from '@/hooks/useSymbols'

interface SymbolSelectorProps {
    selectedSymbols: string[]
    onChange: (symbols: string[]) => void
    maxSymbols?: number
}

export function SymbolSelector({ selectedSymbols, onChange, maxSymbols = 50 }: SymbolSelectorProps) {
    const { filteredSymbols, searchQuery, setSearchQuery, isLoading } = useSymbols()
    const [showDropdown, setShowDropdown] = useState(false)

    const handleSelect = (symbol: string) => {
        if (selectedSymbols.includes(symbol)) {
            onChange(selectedSymbols.filter(s => s !== symbol))
        } else if (selectedSymbols.length < maxSymbols) {
            onChange([...selectedSymbols, symbol])
        }
    }

    const handleSelectAll = () => {
        const toSelect = filteredSymbols.slice(0, maxSymbols - selectedSymbols.length)
        const combined = [...selectedSymbols, ...toSelect]
        const newSymbols = Array.from(new Set(combined))
        onChange(newSymbols)
    }

    const handleClearAll = () => {
        onChange([])
    }

    const toggleDropdown = () => {
        setShowDropdown(!showDropdown)
    }

    return (
        <div className="relative">
            {/* Trigger Button */}
            <button
                type="button"
                onClick={toggleDropdown}
                className="w-full flex items-center justify-between px-3 py-2 border border-slate-200 rounded-lg bg-white text-sm font-medium text-slate-700 hover:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            >
                <span>
                    {selectedSymbols.length === 0
                        ? 'Select symbols...'
                        : `${selectedSymbols.length} symbol${selectedSymbols.length > 1 ? 's' : ''} selected`}
                </span>
                <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            {/* Dropdown */}
            {showDropdown && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 z-10"
                        onClick={() => setShowDropdown(false)}
                    />

                    {/* Dropdown Content */}
                    <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-20 max-h-80 overflow-hidden flex flex-col">
                        {/* Search Input */}
                        <div className="p-2 border-b border-slate-100">
                            <div className="relative">
                                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                </svg>
                                <input
                                    type="text"
                                    placeholder="Search symbols..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    autoFocus
                                />
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex gap-2 p-2 border-b border-slate-100">
                            <button
                                type="button"
                                onClick={handleSelectAll}
                                disabled={filteredSymbols.length === 0 || selectedSymbols.length >= maxSymbols}
                                className="flex-1 px-2 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                Select All
                            </button>
                            <button
                                type="button"
                                onClick={handleClearAll}
                                disabled={selectedSymbols.length === 0}
                                className="flex-1 px-2 py-1.5 text-xs font-medium text-red-600 bg-red-50 rounded-md hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                Clear All
                            </button>
                        </div>

                        {/* Symbol List */}
                        <div className="flex-1 overflow-y-auto p-2">
                            {isLoading ? (
                                <div className="text-center py-4 text-sm text-slate-400">
                                    Loading symbols...
                                </div>
                            ) : filteredSymbols.length === 0 ? (
                                <div className="text-center py-4 text-sm text-slate-400">
                                    No symbols found
                                </div>
                            ) : (
                                <div className="grid grid-cols-2 gap-1">
                                    {filteredSymbols.map(symbol => (
                                        <button
                                            key={symbol}
                                            type="button"
                                            onClick={() => handleSelect(symbol)}
                                            className={`px-2 py-1.5 text-xs font-mono rounded-md text-left transition-colors ${
                                                selectedSymbols.includes(symbol)
                                                    ? 'bg-blue-100 text-blue-700 font-semibold'
                                                    : 'text-slate-600 hover:bg-slate-50'
                                            }`}
                                        >
                                            {symbol}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="p-2 border-t border-slate-100 text-xs text-slate-400 text-center">
                            {selectedSymbols.length} / {maxSymbols} selected
                        </div>
                    </div>
                </>
            )}

            {/* Selected Symbols Chips */}
            {selectedSymbols.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                    {selectedSymbols.slice(0, 10).map(symbol => (
                        <span
                            key={symbol}
                            className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 text-xs font-mono font-semibold rounded-md"
                        >
                            {symbol}
                            <button
                                type="button"
                                onClick={() => onChange(selectedSymbols.filter(s => s !== symbol))}
                                className="hover:text-blue-900 focus:outline-none"
                            >
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </span>
                    ))}
                    {selectedSymbols.length > 10 && (
                        <span className="inline-flex items-center px-2 py-1 bg-slate-100 text-slate-500 text-xs rounded-md">
                            +{selectedSymbols.length - 10} more
                        </span>
                    )}
                </div>
            )}
        </div>
    )
}
