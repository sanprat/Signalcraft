'use client'

import { useEffect, useRef } from 'react'
import type { ValidationResult } from '@/lib/types/strategy'

interface ValidationResultsProps {
    result: ValidationResult | null
    isValidating: boolean
}

export function ValidationResults({ result, isValidating }: ValidationResultsProps) {
    const resultsRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (result && !result.valid && result.errors.length > 0 && resultsRef.current) {
            resultsRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
    }, [result])

    if (isValidating) {
        return (
            <div className="flex items-center justify-center gap-3 p-6 bg-slate-50 rounded-lg">
                <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-slate-600">Validating strategy...</span>
            </div>
        )
    }

    if (!result) {
        return null
    }

    return (
        <div ref={resultsRef} className="space-y-3">
            {/* Success State */}
            {result.valid && result.errors.length === 0 && (
                <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
                    <svg className="w-5 h-5 text-green-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                        <div className="font-medium text-green-800">Strategy is valid!</div>
                        <div className="text-sm text-green-600 mt-1">
                            Your strategy passed all validation checks.
                        </div>
                    </div>
                </div>
            )}

            {/* Errors */}
            {result.errors.length > 0 && (
                <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div className="flex-1">
                        <div className="font-medium text-red-800">
                            {result.errors.length} error{result.errors.length > 1 ? 's' : ''} found
                        </div>
                        <ul className="mt-2 space-y-1">
                            {result.errors.map((error, i) => (
                                <li key={i} className="text-sm text-red-700 flex items-start gap-2">
                                    <span className="text-red-400 mt-0.5">•</span>
                                    <span>{error}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}

            {/* Warnings */}
            {result.warnings.length > 0 && (
                <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                    <svg className="w-5 h-5 text-amber-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div className="flex-1">
                        <div className="font-medium text-amber-800">
                            {result.warnings.length} warning{result.warnings.length > 1 ? 's' : ''}
                        </div>
                        <ul className="mt-2 space-y-1">
                            {result.warnings.map((warning, i) => (
                                <li key={i} className="text-sm text-amber-700 flex items-start gap-2">
                                    <span className="text-amber-400 mt-0.5">•</span>
                                    <span>{warning}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}

            {/* Summary */}
            {result.summary && (
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                        Strategy Summary
                    </div>
                    <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                        <div className="text-slate-500">Name:</div>
                        <div className="font-medium text-slate-700">{result.summary.name}</div>

                        <div className="text-slate-500">Symbols:</div>
                        <div className="font-medium text-slate-700">
                            {result.summary.symbols?.length || 0} selected
                        </div>

                        <div className="text-slate-500">Timeframe:</div>
                        <div className="font-medium text-slate-700">{result.summary.timeframe}</div>

                        <div className="text-slate-500">Entry Logic:</div>
                        <div className="font-medium text-slate-700">{result.summary.entry_logic}</div>

                        <div className="text-slate-500">Entry Conditions:</div>
                        <div className="font-medium text-slate-700">
                            {result.summary.entry_conditions_count}
                        </div>

                        <div className="text-slate-500">Exit Rules:</div>
                        <div className="font-medium text-slate-700">
                            {result.summary.exit_rules_count}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
