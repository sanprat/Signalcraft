'use client'

import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { ExitRule } from '@/lib/types/strategy'

interface ExitRuleCardProps {
    rule: ExitRule
    onUpdate: (updates: Partial<ExitRule>) => void
    onRemove: () => void
    canRemove: boolean
}

export function ExitRuleCard({ rule, onUpdate, onRemove, canRemove }: ExitRuleCardProps) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: rule.id })

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    }

    // Validate and clamp percentage values to reasonable bounds
    const clampPercent = (val: number, min: number, max: number) => {
        if (isNaN(val)) return min
        return Math.min(Math.max(val, min), max)
    }

    const getRuleIcon = () => {
        switch (rule.type) {
            case 'stoploss':
                return (
                    <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
                    </svg>
                )
            case 'target':
                return (
                    <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                )
            case 'trailing':
                return (
                    <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                    </svg>
                )
            case 'time':
                return (
                    <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                )
            default:
                return null
        }
    }

    const getRuleLabel = () => {
        switch (rule.type) {
            case 'stoploss':
                return 'Stop Loss'
            case 'target':
                return 'Target Profit'
            case 'trailing':
                return 'Trailing Stop'
            case 'time':
                return 'Time Exit'
            default:
                return rule.type
        }
    }

    const getRuleColor = () => {
        switch (rule.type) {
            case 'stoploss':
                return 'border-red-200 bg-red-50'
            case 'target':
                return 'border-green-200 bg-green-50'
            case 'trailing':
                return 'border-amber-200 bg-amber-50'
            case 'time':
                return 'border-blue-200 bg-blue-50'
            default:
                return 'border-slate-200 bg-slate-50'
        }
    }

    return (
        <div
            ref={setNodeRef}
            style={style}
            className={`border ${getRuleColor()} rounded-lg p-4 transition-shadow ${
                isDragging ? 'shadow-lg ring-2 ring-blue-200' : ''
            }`}
        >
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    {/* Drag Handle */}
                    <button
                        type="button"
                        className="p-1 text-slate-400 hover:text-slate-600 cursor-grab active:cursor-grabbing"
                        {...attributes}
                        {...listeners}
                        aria-label="Drag to reorder"
                        role="button"
                        tabIndex={0}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                        </svg>
                    </button>
                    {getRuleIcon()}
                    <span className="font-semibold text-slate-700">{getRuleLabel()}</span>
                    <span className="text-xs text-slate-400">Priority {rule.priority}</span>
                </div>

                {canRemove && (
                    <button
                        type="button"
                        onClick={onRemove}
                        className="p-1 text-red-400 hover:text-red-600 hover:bg-red-100 rounded transition-colors"
                        title="Remove rule"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                )}
            </div>

            {/* Rule Configuration */}
            <div className="space-y-3">
                {/* Stop Loss */}
                {rule.type === 'stoploss' && (
                    <>
                        <div className="flex items-center gap-4">
                            <div className="flex-1">
                                <label className="block text-xs font-medium text-slate-500 mb-1">
                                    Stop Loss %
                                </label>
                                <input
                                    type="number"
                                    step="0.1"
                                    min="0.1"
                                    max="50"
                                    value={rule.percent}
                                    onChange={(e) => {
                                        const val = parseFloat(e.target.value)
                                        onUpdate({ percent: clampPercent(val, 0.1, 50) })
                                    }}
                                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
                                />
                            </div>
                            <div className="flex items-center gap-2 pt-5">
                                <input
                                    type="checkbox"
                                    id={`trailing-${rule.id}`}
                                    checked={rule.trailing}
                                    onChange={(e) => onUpdate({ trailing: e.target.checked })}
                                    className="w-4 h-4 text-red-600 border-slate-300 rounded focus:ring-red-500"
                                />
                                <label htmlFor={`trailing-${rule.id}`} className="text-xs text-slate-600">
                                    Trailing
                                </label>
                            </div>
                        </div>
                    </>
                )}

                {/* Target */}
                {rule.type === 'target' && (
                    <div>
                        <label className="block text-xs font-medium text-slate-500 mb-1">
                            Target Profit %
                        </label>
                        <input
                            type="number"
                            step="0.1"
                            min="0.1"
                            max="100"
                            value={rule.percent}
                            onChange={(e) => {
                                const val = parseFloat(e.target.value)
                                onUpdate({ percent: clampPercent(val, 0.1, 100) })
                            }}
                            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                        />
                    </div>
                )}

                {/* Trailing Stop */}
                {rule.type === 'trailing' && (
                    <div className="space-y-3">
                        <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1">
                                Trailing %
                            </label>
                            <input
                                type="number"
                                step="0.1"
                                min="0.1"
                                max="50"
                                value={rule.percent}
                                onChange={(e) => {
                                    const val = parseFloat(e.target.value)
                                    onUpdate({ percent: clampPercent(val, 0.1, 50) })
                                }}
                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1">
                                Activate at Profit %
                            </label>
                            <input
                                type="number"
                                step="0.1"
                                min="0.1"
                                max="100"
                                value={rule.activationPercent || 0}
                                onChange={(e) => {
                                    const val = parseFloat(e.target.value)
                                    onUpdate({ activationPercent: clampPercent(val, 0.1, 100) })
                                }}
                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                            />
                        </div>
                    </div>
                )}

                {/* Time Exit */}
                {rule.type === 'time' && (
                    <div>
                        <label className="block text-xs font-medium text-slate-500 mb-1">
                            Exit Time (IST)
                        </label>
                        <input
                            type="time"
                            value={rule.time}
                            onChange={(e) => onUpdate({ time: e.target.value })}
                            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                    </div>
                )}
            </div>
        </div>
    )
}
