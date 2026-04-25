'use client'

import type { Condition } from '@/lib/types/strategy'
import { IndicatorPicker } from './IndicatorPicker'
import { OperatorPicker } from './OperatorPicker'
import { MathExprBuilder } from './MathExprBuilder'

interface ConditionEditorProps {
    condition: Condition
    onUpdate: (updates: Partial<Condition>) => void
}

export function ConditionEditor({ condition, onUpdate }: ConditionEditorProps) {
    const leftIndicator = condition.left && typeof condition.left === 'object' && 'name' in condition.left
        ? condition.left as { type: string; name: string; params: (number | string)[] }
        : null

    const isCrossoverOperator =
        condition.operator === 'crosses_above' || condition.operator === 'crosses_below'

    const defaultCrossoverRight = (() => {
        if (leftIndicator?.type === 'indicator') {
            const leftPeriod = typeof leftIndicator.params?.[0] === 'number' ? Number(leftIndicator.params[0]) : 20
            const fallbackPeriod = leftPeriod === 20 ? 50 : Math.max(leftPeriod + 30, 2)
            return {
                type: 'indicator' as const,
                name: leftIndicator.name,
                params: [fallbackPeriod],
            }
        }
        return {
            type: 'indicator' as const,
            name: 'SMA',
            params: [50],
        }
    })()

    return (
        <div className="flex flex-wrap items-center gap-3">
            <div className="flex-1 min-w-[200px]">
                <label className="block text-xs font-medium text-slate-500 mb-1">Indicator</label>
                <IndicatorPicker
                    value={
                        leftIndicator && leftIndicator.type === 'indicator'
                            ? { name: leftIndicator.name, params: leftIndicator.params }
                            : { name: 'RSI', params: [14] }
                    }
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
            </div>

            <div className="min-w-[150px]">
                <label className="block text-xs font-medium text-slate-500 mb-1">Operator</label>
                <OperatorPicker
                    value={condition.operator}
                    onChange={(operator) => {
                        if (
                            (operator === 'crosses_above' || operator === 'crosses_below') &&
                            (!condition.right || typeof condition.right !== 'object' || !('type' in condition.right) || condition.right.type !== 'indicator')
                        ) {
                            onUpdate({
                                operator,
                                right: defaultCrossoverRight,
                            })
                            return
                        }
                        onUpdate({ operator })
                    }}
                />
            </div>

            <div className="flex-1 min-w-[150px]">
                <label className="block text-xs font-medium text-slate-500 mb-1">Value / Indicator</label>
                <MathExprBuilder
                    value={condition.right}
                    onChange={(right) => onUpdate({ right })}
                    side="right"
                    allowValueMode={!isCrossoverOperator}
                />
                {isCrossoverOperator && (
                    <div className="mt-1 text-[11px] text-slate-400">
                        Crossover compares two series. Value mode is disabled here.
                    </div>
                )}
            </div>
        </div>
    )
}
