'use client'

import { useState, useEffect } from 'react'
import { DATE_PRESETS } from '@/lib/types/strategy'

interface DateRangePickerProps {
    startDate: string
    endDate: string
    onChange: (startDate: string, endDate: string) => void
}

export function DateRangePicker({ startDate, endDate, onChange }: DateRangePickerProps) {
    const [activePreset, setActivePreset] = useState<string | null>(null)

    const applyPreset = (preset: typeof DATE_PRESETS[0]) => {
        const today = new Date()
        let start: Date
        const end = today.toISOString().split('T')[0]

        if (preset.days === -1) {
            // Year to date
            start = new Date(today.getFullYear(), 0, 1)
        } else if (preset.days === -2) {
            // All time (2 years)
            start = new Date(today.getFullYear() - 2, 0, 1)
        } else {
            start = new Date(today.getTime() - preset.days * 24 * 60 * 60 * 1000)
        }

        onChange(start.toISOString().split('T')[0], end)
        setActivePreset(preset.label)
    }

    const handleStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        onChange(e.target.value, endDate)
        setActivePreset(null)
    }

    const handleEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        onChange(startDate, e.target.value)
        setActivePreset(null)
    }

    return (
        <div className="space-y-3">
            {/* Preset Buttons */}
            <div className="flex flex-wrap gap-2">
                {DATE_PRESETS.map(preset => (
                    <button
                        key={preset.label}
                        type="button"
                        onClick={() => applyPreset(preset)}
                        className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                            activePreset === preset.label
                                ? 'bg-blue-600 text-white'
                                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                    >
                        {preset.label}
                    </button>
                ))}
            </div>

            {/* Date Inputs */}
            <div className="flex items-center gap-3">
                <div className="flex-1">
                    <label className="block text-xs font-medium text-slate-500 mb-1">
                        From
                    </label>
                    <input
                        type="date"
                        value={startDate}
                        onChange={handleStartChange}
                        max={endDate}
                        className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>
                <div className="text-slate-400 mt-5">→</div>
                <div className="flex-1">
                    <label className="block text-xs font-medium text-slate-500 mb-1">
                        To
                    </label>
                    <input
                        type="date"
                        value={endDate}
                        onChange={handleEndChange}
                        min={startDate}
                        max={new Date().toISOString().split('T')[0]}
                        className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>
            </div>
        </div>
    )
}
