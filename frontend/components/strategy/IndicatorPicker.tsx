'use client'

import { useState, useRef, useEffect } from 'react'
import { INDICATORS_LIST } from '@/lib/types/strategy'
import type { IndicatorName, IndicatorDefinition } from '@/lib/types/strategy'

interface IndicatorPickerProps {
    value: {
        name: string
        params: (number | string)[]
    }
    onChange: (indicator: { name: string; params: (number | string)[] }) => void
}

export function IndicatorPicker({ value, onChange }: IndicatorPickerProps) {
    const [isOpen, setIsOpen] = useState(false)
    const [search, setSearch] = useState('')
    const dropdownRef = useRef<HTMLDivElement>(null)

    const indicatorDef = INDICATORS_LIST.find(i => i.name === value.name)

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }

        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    const filteredIndicators = INDICATORS_LIST.filter(ind =>
        ind.name.toLowerCase().includes(search.toLowerCase()) ||
        ind.description.toLowerCase().includes(search.toLowerCase())
    )

    const handleSelect = (indicator: IndicatorDefinition) => {
        const defaultParams = indicator.params.map(p => p.default)
        onChange({ name: indicator.name, params: defaultParams })
        setIsOpen(false)
        setSearch('')
    }

    const handleParamChange = (index: number, newValue: string) => {
        const newParams = [...value.params]
        newParams[index] = parseFloat(newValue) || 0
        onChange({ ...value, params: newParams })
    }

    return (
        <div ref={dropdownRef} className="relative">
            {/* Trigger */}
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center justify-between px-3 py-2 border border-slate-200 rounded-lg bg-white text-sm hover:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            >
                <span className="font-medium text-slate-700">
                    {value.name || 'Select indicator'}
                </span>
                <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            {/* Dropdown */}
            {isOpen && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-20 max-h-80 overflow-hidden">
                    {/* Search */}
                    <div className="p-2 border-b border-slate-100">
                        <input
                            type="text"
                            placeholder="Search indicators..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            autoFocus
                        />
                    </div>

                    {/* List */}
                    <div className="max-h-60 overflow-y-auto">
                        {filteredIndicators.map(indicator => (
                            <button
                                key={indicator.name}
                                type="button"
                                onClick={() => handleSelect(indicator)}
                                className={`w-full px-3 py-2 text-left hover:bg-slate-50 transition-colors ${
                                    value.name === indicator.name ? 'bg-blue-50' : ''
                                }`}
                            >
                                <div className="font-medium text-slate-700 text-sm">
                                    {indicator.name}
                                </div>
                                <div className="text-xs text-slate-400">
                                    {indicator.description}
                                </div>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Parameters */}
            {indicatorDef && indicatorDef.params.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                    {indicatorDef.params.map((param, index) => (
                        <div key={param.name} className="flex items-center gap-1">
                            <span className="text-xs text-slate-500 font-medium">
                                {param.name}:
                            </span>
                            <input
                                type="number"
                                value={value.params[index] ?? param.default}
                                onChange={(e) => handleParamChange(index, e.target.value)}
                                className="w-16 px-2 py-1 text-xs border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            />
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
