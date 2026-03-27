'use client'

import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { Condition, MathOperand } from '@/lib/types/strategy'
import { IndicatorPicker } from './IndicatorPicker'
import { OperatorPicker } from './OperatorPicker'
import { MathExprBuilder } from './MathExprBuilder'

interface ConditionBlockProps {
    condition: Condition
    index: number
    onUpdate: (updates: Partial<Condition>) => void
    onRemove: () => void
    canRemove: boolean
}

export function ConditionBlock({
    condition,
    index,
    onUpdate,
    onRemove,
    canRemove,
}: ConditionBlockProps) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: condition.id })

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    }

    // Left side indicator info
    const leftIndicator = condition.left && typeof condition.left === 'object' && 'name' in condition.left
        ? condition.left as { type: string; name: string; params: (number | string)[] }
        : null

    return (
        <div
            ref={setNodeRef}
            style={style}
            className={`bg-white border border-slate-200 rounded-lg p-4 transition-shadow ${
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
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                        </svg>
                    </button>
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                        Condition {index + 1}
                    </span>
                </div>

                {canRemove && (
                    <button
                        type="button"
                        onClick={onRemove}
                        className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                        title="Remove condition"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                )}
            </div>

            {/* Condition Builder */}
            <div className="flex flex-wrap items-center gap-3">
                {/* Left Side - Indicator */}
                <div className="flex-1 min-w-[200px]">
                    <label className="block text-xs font-medium text-slate-500 mb-1">Indicator</label>
                    {leftIndicator && leftIndicator.type === 'indicator' ? (
                        <IndicatorPicker
                            value={{ name: leftIndicator.name, params: leftIndicator.params }}
                            onChange={(newIndicator) => {
                                onUpdate({
                                    left: {
                                        type: 'indicator',
                                        name: newIndicator.name,
                                        params: newIndicator.params,
                                    },
                                })
                            }}
                        />
                    ) : (
                        <IndicatorPicker
                            value={{ name: 'RSI', params: [14] }}
                            onChange={(newIndicator) => {
                                onUpdate({
                                    left: {
                                        type: 'indicator',
                                        name: newIndicator.name,
                                        params: newIndicator.params,
                                    },
                                })
                            }}
                        />
                    )}
                </div>

                {/* Operator */}
                <div className="min-w-[150px]">
                    <label className="block text-xs font-medium text-slate-500 mb-1">Operator</label>
                    <OperatorPicker
                        value={condition.operator}
                        onChange={(operator) => onUpdate({ operator })}
                    />
                </div>

                {/* Right Side - Value */}
                <div className="flex-1 min-w-[150px]">
                    <label className="block text-xs font-medium text-slate-500 mb-1">Value / Indicator</label>
                    <MathExprBuilder
                        value={condition.right}
                        onChange={(right) => onUpdate({ right })}
                        side="right"
                    />
                </div>
            </div>

            {/* Preview */}
            <div className="mt-3 pt-3 border-t border-slate-100">
                <code className="text-xs text-slate-500 font-mono">
                    {leftIndicator?.name || 'Indicator'}
                    {leftIndicator?.params ? `(${leftIndicator.params.join(', ')})` : ''}
                    {' '}
                    <span className="text-blue-600">
                        {condition.operator === '<' ? '<' :
                         condition.operator === '>' ? '>' :
                         condition.operator === '<=' ? '≤' :
                         condition.operator === '>=' ? '≥' :
                         condition.operator === '==' ? '=' :
                         condition.operator === '!=' ? '≠' : condition.operator}
                    </span>
                    {' '}
                    {typeof condition.right === 'object' && condition.right && 'type' in condition.right
                        ? condition.right.type === 'value'
                            ? (condition.right as any).value
                            : `${(condition.right as any).name || 'Indicator'}${((condition.right as any).params?.length ? `(${(condition.right as any).params.join(', ')})` : '')}`
                        : condition.right}
                </code>
            </div>
        </div>
    )
}
