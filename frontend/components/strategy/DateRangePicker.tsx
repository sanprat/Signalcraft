'use client'

import { useState, useEffect } from 'react'
import { DATE_PRESETS } from '@/lib/types/strategy'
import { isValidDateString } from '@/lib/date'

interface DateRangePickerProps {
    startDate: string
    endDate: string
    onChange: (startDate: string, endDate: string) => void
}

export function DateRangePicker({ startDate, endDate, onChange }: DateRangePickerProps) {
    const [activePreset, setActivePreset] = useState<string | null>(null)
    const [draftStartDate, setDraftStartDate] = useState(startDate)
    const [draftEndDate, setDraftEndDate] = useState(endDate)

    useEffect(() => {
        setDraftStartDate(startDate)
    }, [startDate])

    useEffect(() => {
        setDraftEndDate(endDate)
    }, [endDate])

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
        setDraftStartDate(start.toISOString().split('T')[0])
        setDraftEndDate(end)
        setActivePreset(preset.label)
    }

    const handleStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const nextValue = e.target.value
        setDraftStartDate(nextValue)
        if (isValidDateString(nextValue) && isValidDateString(draftEndDate)) {
            onChange(nextValue, draftEndDate)
        }
        setActivePreset(null)
    }

    const handleEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const nextValue = e.target.value
        setDraftEndDate(nextValue)
        if (isValidDateString(draftStartDate) && isValidDateString(nextValue)) {
            onChange(draftStartDate, nextValue)
        }
        setActivePreset(null)
    }

    const handleStartBlur = () => {
        if (!draftStartDate || isValidDateString(draftStartDate)) {
            return
        }
        setDraftStartDate(startDate)
    }

    const handleEndBlur = () => {
        if (!draftEndDate || isValidDateString(draftEndDate)) {
            return
        }
        setDraftEndDate(endDate)
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
                        value={draftStartDate}
                        onChange={handleStartChange}
                        onBlur={handleStartBlur}
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
                        value={draftEndDate}
                        onChange={handleEndChange}
                        onBlur={handleEndBlur}
                        min={startDate}
                        max={new Date().toISOString().split('T')[0]}
                        className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>
            </div>
        </div>
    )
}
