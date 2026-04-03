'use client'

import { useState, useMemo } from 'react'
import type { StrategyV2 } from '@/lib/types/strategy'

interface ZenScriptPreviewProps {
    strategy: StrategyV2
}

export function ZenScriptPreview({ strategy }: ZenScriptPreviewProps) {
    const [isExpanded, setIsExpanded] = useState(true)
    const [copied, setCopied] = useState(false)

    const zenscript = useMemo(() => generateZenScript(strategy), [strategy])

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(zenscript)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        } catch (err) {
            console.error('Failed to copy:', err)
        }
    }

    return (
        <div className="bg-slate-900 rounded-lg overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-slate-800">
                <button
                    type="button"
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="flex items-center gap-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
                >
                    <svg
                        className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                    ZenScript Preview
                </button>

                <button
                    type="button"
                    onClick={handleCopy}
                    className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
                >
                    {copied ? (
                        <>
                            <svg className="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            Copied!
                        </>
                    ) : (
                        <>
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                            </svg>
                            Copy
                        </>
                    )}
                </button>
            </div>

            {/* Content */}
            {isExpanded && (
                <div className="p-4">
                    <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap overflow-x-auto">
                        {zenscript}
                    </pre>
                </div>
            )}
        </div>
    )
}

function generateZenScript(strategy: StrategyV2): string {
    const lines: string[] = []
    const indent = '    '

    // Strategy declaration
    lines.push(`STRATEGY "${strategy.name || 'Untitled Strategy'}" {`)

    // Symbols
    const symbols = Array.isArray(strategy.symbols) ? strategy.symbols : []
    lines.push(`${indent}SYMBOLS: ${symbols.join(', ') || 'N/A'}`)

    // Asset type specific
    if (strategy.asset_type === 'FNO') {
        lines.push(`${indent}INDEX: ${strategy.index || 'NIFTY'}`)
        lines.push(`${indent}OPTION: ${strategy.option_type || 'CE'}`)
        if (strategy.strike_type) {
            lines.push(`${indent}STRIKE: ${strategy.strike_type}`)
        }
    }

    // Timeframe
    lines.push(`${indent}TIMEFRAME: ${strategy.timeframe || '1min'}`)

    // Date range
    if (strategy.backtest_from && strategy.backtest_to) {
        lines.push(`${indent}DATE_RANGE: ${strategy.backtest_from} to ${strategy.backtest_to}`)
    }

    // Entry conditions
    lines.push('')
    lines.push(`${indent}ENTRY ${strategy.entry_logic || 'AND'} {`)
    const entryConditions = Array.isArray(strategy.entry_conditions) ? strategy.entry_conditions : []
    if (entryConditions.length === 0) {
        lines.push(`${indent}${indent}// No entry conditions configured`)
    } else {
        entryConditions.forEach((cond, i) => {
            const leftSide = formatConditionSide(cond.left)
            const rightSide = formatConditionSide(cond.right)
            const operator = formatOperator(cond.operator)
            lines.push(`${indent}${indent}${leftSide} ${operator} ${rightSide}`)
        })
    }
    lines.push(`${indent}}`)

    // Exit rules - with proper null/undefined handling
    lines.push('')
    const exitLogic = strategy.exit_logic || 'ALL'
    lines.push(`${indent}EXIT ${exitLogic} {`)
    
    const exitRules = strategy.exit_rules || []
    
    if (exitRules.length === 0) {
        lines.push(`${indent}${indent}// No exit rules configured`)
    } else {
        exitRules.forEach((rule) => {
            lines.push(`${indent}${indent}${formatExitRule(rule)}`)
        })
    }
    lines.push(`${indent}}`)

    // Risk configuration
    lines.push('')
    lines.push(`${indent}RISK {`)
    lines.push(
        `${indent}${indent}MAX_TRADES_DAY: ${
            strategy.risk.max_trades_per_day > 0
                ? strategy.risk.max_trades_per_day
                : 'NO_LIMIT'
        }`
    )
    lines.push(
        `${indent}${indent}MAX_DAILY_LOSS: ${
            strategy.risk.max_loss_per_day > 0
                ? `₹${strategy.risk.max_loss_per_day.toLocaleString()}`
                : 'NO_CAP'
        }`
    )
    lines.push(`${indent}${indent}QUANTITY: ${strategy.risk.quantity}`)
    if (strategy.risk.max_concurrent_trades > 1) {
        lines.push(`${indent}${indent}MAX_POSITIONS: ${strategy.risk.max_concurrent_trades}`)
    }
    if (strategy.risk.reentry_after_sl) {
        lines.push(`${indent}${indent}REENTRY_AFTER_SL: true`)
    }
    if (strategy.risk.partial_exit_pct) {
        lines.push(`${indent}${indent}PARTIAL_EXIT: ${strategy.risk.partial_exit_pct}%`)
    }
    lines.push(`${indent}}`)

    lines.push('}')

    return lines.join('\n')
}

function formatConditionSide(side: any): string {
    if (!side) return 'N/A'

    if (typeof side === 'number') return side.toString()
    if (typeof side === 'string') return side

    if (side.type === 'value') return side.value.toString()
    if (side.type === 'price') return side.field.toUpperCase()
    if (side.type === 'indicator') {
        const params = side.params?.length ? `(${side.params.join(', ')})` : ''
        return `${side.name}${params}`
    }
    if (side.type === 'math') {
        const left = formatConditionSide(side.left)
        const right = formatConditionSide(side.right)
        return `(${left} ${side.operator} ${right})`
    }

    return 'N/A'
}

function formatOperator(op: string): string {
    const opMap: Record<string, string> = {
        '<': 'LT',
        '>': 'GT',
        '<=': 'LTE',
        '>=': 'GTE',
        '==': 'EQ',
        '!=': 'NEQ',
        'crosses_above': 'CROSSES_ABOVE',
        'crosses_below': 'CROSSES_BELOW',
    }
    return opMap[op] || op
}

function formatExitRule(rule: any): string {
    // Handle null/undefined rule
    if (!rule) {
        return '// Invalid rule'
    }
    
    // Handle missing type
    if (!rule.type) {
        return `// Invalid rule: ${JSON.stringify(rule).slice(0, 50)}...`
    }
    
    try {
        switch (rule.type) {
            case 'stoploss':
                return `STOPLOSS: ${rule.percent || 0}%${rule.trailing ? ' (trailing)' : ''}`
            case 'target':
                return `TARGET: ${rule.percent || 0}%`
            case 'trailing':
                return `TRAILING: ${rule.percent || 0}%${rule.activationPercent ? ` (activate at ${rule.activationPercent}%)` : ''}`
            case 'time':
                return `TIME: ${rule.time || '00:00'}`
            default:
                return `// Unknown rule type: ${rule.type}`
        }
    } catch (err) {
        return `// Error formatting rule`
    }
}
