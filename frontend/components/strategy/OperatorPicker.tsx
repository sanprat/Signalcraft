'use client'

import { OPERATORS } from '@/lib/types/strategy'
import type { ComparisonOperator } from '@/lib/types/strategy'

interface OperatorPickerProps {
    value: ComparisonOperator
    onChange: (operator: ComparisonOperator) => void
}

export function OperatorPicker({ value, onChange }: OperatorPickerProps) {
    return (
        <div className="relative">
            <select
                value={value}
                onChange={(e) => onChange(e.target.value as ComparisonOperator)}
                className="appearance-none px-3 py-2 pr-8 border border-slate-200 rounded-lg bg-white text-sm font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent cursor-pointer transition-all hover:border-blue-400"
            >
                {OPERATORS.map(op => (
                    <option key={op.value} value={op.value}>
                        {op.symbol} {op.label}
                    </option>
                ))}
            </select>
            <svg
                className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
            >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
        </div>
    )
}
