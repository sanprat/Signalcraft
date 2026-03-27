'use client'

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
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import type { Condition, LogicType } from '@/lib/types/strategy'
import { ConditionBlock } from './ConditionBlock'
import { createDefaultCondition } from '@/lib/types/strategy'

interface EntryBuilderProps {
    conditions: Condition[]
    entryLogic: LogicType
    onAddCondition: (condition?: Condition) => void
    onRemoveCondition: (conditionId: string) => void
    onUpdateCondition: (conditionId: string, updates: Partial<Condition>) => void
    onReorderConditions: (startIndex: number, endIndex: number) => void
    onSetEntryLogic: (logic: LogicType) => void
}

export function EntryBuilder({
    conditions,
    entryLogic,
    onAddCondition,
    onRemoveCondition,
    onUpdateCondition,
    onReorderConditions,
    onSetEntryLogic,
}: EntryBuilderProps) {
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
            const oldIndex = conditions.findIndex(c => c.id === active.id)
            const newIndex = conditions.findIndex(c => c.id === over.id)
            onReorderConditions(oldIndex, newIndex)
        }
    }

    const handleAddCondition = () => {
        const newCondition = createDefaultCondition()
        onAddCondition(newCondition)
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-base font-semibold text-slate-800">Entry Conditions</h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                        Define when the strategy should enter a trade
                    </p>
                </div>

                {/* Logic Toggle */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Match:</span>
                    <div className="flex bg-slate-100 rounded-lg p-0.5">
                        <button
                            type="button"
                            onClick={() => onSetEntryLogic('ALL')}
                            className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                                entryLogic === 'ALL'
                                    ? 'bg-blue-600 text-white shadow'
                                    : 'text-slate-600 hover:text-slate-800'
                            }`}
                        >
                            ALL
                        </button>
                        <button
                            type="button"
                            onClick={() => onSetEntryLogic('ANY')}
                            className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                                entryLogic === 'ANY'
                                    ? 'bg-blue-600 text-white shadow'
                                    : 'text-slate-600 hover:text-slate-800'
                            }`}
                        >
                            ANY
                        </button>
                    </div>
                </div>
            </div>

            {/* Conditions */}
            <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
            >
                <SortableContext
                    items={conditions.map(c => c.id)}
                    strategy={verticalListSortingStrategy}
                >
                    <div className="space-y-3">
                        {conditions.length === 0 ? (
                            <div className="text-center py-8 px-4 border-2 border-dashed border-slate-200 rounded-lg bg-slate-50">
                                <svg className="w-8 h-8 text-slate-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                                </svg>
                                <p className="text-sm text-slate-500">No conditions added yet</p>
                                <p className="text-xs text-slate-400 mt-1">
                                    {entryLogic === 'ALL'
                                        ? 'All conditions must be met for entry'
                                        : 'Any condition can trigger entry'}
                                </p>
                            </div>
                        ) : (
                            conditions.map((condition, index) => (
                                <ConditionBlock
                                    key={condition.id}
                                    condition={condition}
                                    index={index}
                                    onUpdate={(updates) => onUpdateCondition(condition.id, updates)}
                                    onRemove={() => onRemoveCondition(condition.id)}
                                    canRemove={conditions.length > 1}
                                />
                            ))
                        )}
                    </div>
                </SortableContext>
            </DndContext>

            {/* Add Button */}
            <button
                type="button"
                onClick={handleAddCondition}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-slate-300 rounded-lg text-sm font-medium text-slate-600 hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
            >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                Add Entry Condition
            </button>

            {/* Logic Help Text */}
            {conditions.length > 1 && (
                <div className={`px-3 py-2 rounded-lg text-xs ${
                    entryLogic === 'ALL'
                        ? 'bg-blue-50 text-blue-700'
                        : 'bg-amber-50 text-amber-700'
                }`}>
                    {entryLogic === 'ALL' ? (
                        <span>
                            <strong>ALL:</strong> All {conditions.length} conditions must be true for entry
                        </span>
                    ) : (
                        <span>
                            <strong>ANY:</strong> Entry triggers when any {conditions.length} conditions are true
                        </span>
                    )}
                </div>
            )}
        </div>
    )
}
