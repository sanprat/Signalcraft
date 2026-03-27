'use client'

import { TIMEFRAMES } from '@/lib/types/strategy'
import type { TimeframeType } from '@/lib/types/strategy'

interface TimeframeSelectorProps {
    value: TimeframeType
    onChange: (timeframe: TimeframeType) => void
    assetType?: 'EQUITY' | 'FNO'
}

export function TimeframeSelector({ value, onChange, assetType = 'EQUITY' }: TimeframeSelectorProps) {
    const timeframes = assetType === 'FNO'
        ? TIMEFRAMES.filter(t => ['1m', '5m', '15m', '30m'].includes(t.value))
        : TIMEFRAMES

    return (
        <div className="grid grid-cols-4 gap-2">
            {timeframes.map(tf => (
                <button
                    key={tf.value}
                    type="button"
                    onClick={() => onChange(tf.value)}
                    title={tf.description}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                        value === tf.value
                            ? 'bg-blue-600 text-white shadow-md'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                >
                    <div>{tf.label}</div>
                </button>
            ))}
        </div>
    )
}
