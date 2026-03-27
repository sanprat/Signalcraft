'use client'

import { useState } from 'react'
import type { MathOperand, MathExpr, PriceField } from '@/lib/types/strategy'

interface MathExprBuilderProps {
    value: MathOperand
    onChange: (value: MathOperand) => void
    side: 'left' | 'right'
}

const PRICE_FIELDS: { value: PriceField; label: string }[] = [
    { value: 'close', label: 'Close' },
    { value: 'open', label: 'Open' },
    { value: 'high', label: 'High' },
    { value: 'low', label: 'Low' },
    { value: 'volume', label: 'Volume' },
    { value: 'hl2', label: 'HL2' },
    { value: 'hlc3', label: 'HLC3' },
]

export function MathExprBuilder({ value, onChange, side }: MathExprBuilderProps) {
    const [mode, setMode] = useState<'simple' | 'expression'>('simple')

    const renderValue = () => {
        if (typeof value === 'number' || typeof value === 'string') {
            return (
                <input
                    type="number"
                    value={value}
                    onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
                    className="w-20 px-2 py-1.5 text-sm border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Value"
                />
            )
        }

        if (!value || typeof value !== 'object') {
            return (
                <input
                    type="number"
                    value={0}
                    onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
                    className="w-20 px-2 py-1.5 text-sm border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Value"
                />
            )
        }

        const ref = value as any

        if (ref.type === 'value') {
            return (
                <input
                    type="number"
                    value={ref.value}
                    onChange={(e) => onChange({ type: 'value', value: parseFloat(e.target.value) || 0 })}
                    className="w-20 px-2 py-1.5 text-sm border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Value"
                />
            )
        }

        if (ref.type === 'price') {
            return (
                <select
                    value={ref.field}
                    onChange={(e) => onChange({ type: 'price', field: e.target.value as PriceField })}
                    className="px-2 py-1.5 text-sm border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                    {PRICE_FIELDS.map(f => (
                        <option key={f.value} value={f.value}>{f.label}</option>
                    ))}
                </select>
            )
        }

        if (ref.type === 'indicator') {
            return (
                <div className="flex items-center gap-1">
                    <span className="px-2 py-1.5 text-sm font-mono font-semibold bg-blue-50 text-blue-700 rounded">
                        {ref.name}({ref.params?.join(', ')})
                    </span>
                </div>
            )
        }

        return null
    }

    return (
        <div className="space-y-2">
            {/* Mode Toggle */}
            <div className="flex gap-1">
                <button
                    type="button"
                    onClick={() => setMode('simple')}
                    className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                        mode === 'simple'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                    }`}
                >
                    Simple
                </button>
                <button
                    type="button"
                    onClick={() => setMode('expression')}
                    className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                        mode === 'expression'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                    }`}
                >
                    Indicator
                </button>
            </div>

            {/* Value Input */}
            {renderValue()}
        </div>
    )
}
