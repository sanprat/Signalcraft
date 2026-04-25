'use client'

import { useState } from 'react'
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent,
} from '@dnd-kit/core'
import {
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import type { ExitRule, ExitRuleType, LogicType } from '@/lib/types/strategy'
import { ExitRuleCard } from './ExitRuleCard'
import { createDefaultExitRule } from '@/lib/types/strategy'

interface ExitBuilderProps {
    exitRules: ExitRule[]
    exitLogic: LogicType
    onAddExitRule: (type: ExitRuleType) => void
    onRemoveExitRule: (ruleId: string) => void
    onUpdateExitRule: (ruleId: string, updates: Partial<ExitRule>) => void
    onReorderExitRules: (startIndex: number, endIndex: number) => void
    onSetExitLogic: (logic: LogicType) => void
}

const EXIT_RULE_TYPES: { type: ExitRuleType; label: string; icon: JSX.Element; description: string }[] = [
    {
        type: 'stoploss',
        label: 'Stop Loss',
        icon: (
            <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
            </svg>
        ),
        description: 'Exit when price drops',
    },
    {
        type: 'target',
        label: 'Target',
        icon: (
            <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
        ),
        description: 'Take profit at target',
    },
    {
        type: 'trailing',
        label: 'Trailing Stop',
        icon: (
            <svg className="w-4 h-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
            </svg>
        ),
        description: 'Lock in profits dynamically',
    },
    {
        type: 'time',
        label: 'Time Exit',
        icon: (
            <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
        ),
        description: 'Exit at specific time',
    },
    {
        type: 'indicator_exit',
        label: 'Indicator Exit',
        icon: (
            <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4-4 4 2 8-8" />
            </svg>
        ),
        description: 'Exit on indicator condition',
    },
]

export function ExitBuilder({
    exitRules,
    exitLogic,
    onAddExitRule,
    onRemoveExitRule,
    onUpdateExitRule,
    onReorderExitRules,
    onSetExitLogic,
}: ExitBuilderProps) {
    const [showAddMenu, setShowAddMenu] = useState(false)

    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 8,
            },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    )

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event

        if (over && active.id !== over.id) {
            const oldIndex = exitRules.findIndex(r => r.id === active.id)
            const newIndex = exitRules.findIndex(r => r.id === over.id)
            onReorderExitRules(oldIndex, newIndex)
        }
    }

    const handleAddRule = (type: ExitRuleType) => {
        onAddExitRule(type)
        setShowAddMenu(false)
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-base font-semibold text-slate-800">Exit Rules</h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                        Define when the strategy should exit trades
                    </p>
                </div>

                {/* Logic Toggle */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Exit on:</span>
                    <div className="flex bg-slate-100 rounded-lg p-0.5">
                        <button
                            type="button"
                            onClick={() => onSetExitLogic('ALL')}
                            className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                                exitLogic === 'ALL'
                                    ? 'bg-blue-600 text-white shadow'
                                    : 'text-slate-600 hover:text-slate-800'
                            }`}
                        >
                            ALL
                        </button>
                        <button
                            type="button"
                            onClick={() => onSetExitLogic('ANY')}
                            className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                                exitLogic === 'ANY'
                                    ? 'bg-blue-600 text-white shadow'
                                    : 'text-slate-600 hover:text-slate-800'
                            }`}
                        >
                            ANY
                        </button>
                    </div>
                </div>
            </div>

            {/* Exit Rules List */}
            <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
            >
                <SortableContext
                    items={exitRules.map(r => r.id)}
                    strategy={verticalListSortingStrategy}
                >
                    <div className="space-y-3">
                        {exitRules.length === 0 ? (
                            <div className="text-center py-8 px-4 border-2 border-dashed border-slate-200 rounded-lg bg-slate-50">
                                <svg className="w-8 h-8 text-slate-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                                </svg>
                                <p className="text-sm text-slate-500">No exit rules added yet</p>
                                <p className="text-xs text-slate-400 mt-1">
                                    Add rules below to define exit conditions
                                </p>
                            </div>
                        ) : (
                            exitRules.map((rule) => (
                                <ExitRuleCard
                                    key={rule.id}
                                    rule={rule}
                                    onUpdate={(updates) => onUpdateExitRule(rule.id, updates)}
                                    onRemove={() => onRemoveExitRule(rule.id)}
                                    canRemove={exitRules.length > 1}
                                />
                            ))
                        )}
                    </div>
                </SortableContext>
            </DndContext>

            {/* Add Exit Rule Button */}
            <div className="relative" style={{ zIndex: 1 }}>
                <button
                    type="button"
                    onClick={(e) => {
                        try {
                            e.stopPropagation()
                            setShowAddMenu(!showAddMenu)
                        } catch (err) {
                            console.error('[ExitBuilder] Error toggling menu:', err)
                        }
                    }}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-slate-300 rounded-lg text-sm font-medium text-slate-600 hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-colors cursor-pointer"
                    aria-label="Add exit rule"
                    aria-expanded={showAddMenu}
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                    Add Exit Rule
                </button>

                {/* Add Menu Dropdown - Fixed z-index and event handling */}
                {showAddMenu && (
                    <>
                        {/* Backdrop - click to close */}
                        <div
                            className="fixed inset-0 z-40"
                            onClick={(e) => {
                                e.stopPropagation()
                                setShowAddMenu(false)
                            }}
                            aria-hidden="true"
                        />
                        {/* Dropdown Menu */}
                        <div 
                            className="absolute top-full left-0 right-0 mt-2 bg-white border border-slate-200 rounded-lg shadow-xl z-[100] p-2 space-y-1 pointer-events-auto"
                            style={{ zIndex: 100 }}
                            onClick={(e) => {
                                e.stopPropagation()
                            }}
                        >
                            {EXIT_RULE_TYPES.map(({ type, label, icon, description }) => (
                                <button
                                    key={type}
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        try {
                                            handleAddRule(type)
                                        } catch (err) {
                                            console.error('[ExitBuilder] Error in handleAddRule:', err)
                                        }
                                    }}
                                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-blue-50 hover:text-blue-700 transition-colors text-left cursor-pointer"
                                >
                                    {icon}
                                    <div>
                                        <div className="text-sm font-medium text-slate-700">{label}</div>
                                        <div className="text-xs text-slate-400">{description}</div>
                                    </div>
                                </button>
                            ))}
                        </div>
                    </>
                )}
            </div>

            {/* Exit Logic Help */}
            {exitRules.length > 1 && (
                <div className={`px-3 py-2 rounded-lg text-xs ${
                    exitLogic === 'ANY'
                        ? 'bg-green-50 text-green-700'
                        : 'bg-blue-50 text-blue-700'
                }`}>
                    {exitLogic === 'ANY' ? (
                        <span>
                            <strong>ANY:</strong> Exit when any {exitRules.length} conditions are met
                        </span>
                    ) : (
                        <span>
                            <strong>ALL:</strong> Exit when all {exitRules.length} conditions are met
                        </span>
                    )}
                </div>
            )}

            {/* Priority Note */}
            {exitRules.length > 0 && (
                <div className="text-xs text-slate-400 bg-slate-50 px-3 py-2 rounded-lg">
                    Rules are executed in priority order (1 = highest). Drag rules to reorder.
                </div>
            )}
        </div>
    )
}
