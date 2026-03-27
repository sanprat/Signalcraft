'use client'

import { useState, useCallback, useMemo } from 'react'
import type {
    StrategyV2,
    Condition,
    ExitRule,
    ExitRuleType,
    RiskConfig,
    LogicType,
    TimeframeType,
    AssetType,
    ValidationResult,
    MathOperand,
    ComparisonOperator,
} from '@/lib/types/strategy'
import {
    createDefaultStrategy,
    createDefaultCondition,
    createDefaultExitRule,
    DEFAULT_RISK_CONFIG,
} from '@/lib/types/strategy'
import {
    validateStrategy,
    saveStrategy,
    backtestStrategy,
} from '@/lib/api/strategy'

export interface UseStrategyReturn {
    // State
    strategy: StrategyV2
    isDirty: boolean
    isValidating: boolean
    isSaving: boolean
    isBacktesting: boolean
    validationResult: ValidationResult | null
    editMode: boolean
    strategyId: string | null

    // Strategy actions
    setStrategy: (strategy: StrategyV2) => void
    updateStrategyField: <K extends keyof StrategyV2>(field: K, value: StrategyV2[K]) => void
    loadStrategy: (strategy: StrategyV2, id?: string) => void
    resetStrategy: () => void

    // Entry conditions
    addCondition: (condition?: Condition) => void
    removeCondition: (conditionId: string) => void
    updateCondition: (conditionId: string, updates: Partial<Condition>) => void
    reorderConditions: (startIndex: number, endIndex: number) => void
    setEntryLogic: (logic: LogicType) => void

    // Exit rules
    addExitRule: (type: ExitRuleType) => void
    removeExitRule: (ruleId: string) => void
    updateExitRule: (ruleId: string, updates: Partial<ExitRule>) => void
    reorderExitRules: (startIndex: number, endIndex: number) => void
    setExitLogic: (logic: LogicType) => void

    // Risk config
    updateRisk: (updates: Partial<RiskConfig>) => void

    // API actions
    validate: () => Promise<ValidationResult | null>
    save: () => Promise<string | null>
    backtest: () => Promise<any | null>
}

export function useStrategy(): UseStrategyReturn {
    const [strategy, setStrategyState] = useState<StrategyV2>(createDefaultStrategy())
    const [isDirty, setIsDirty] = useState(false)
    const [isValidating, setIsValidating] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [isBacktesting, setIsBacktesting] = useState(false)
    const [validationResult, setValidationResult] = useState<ValidationResult | null>(null)
    const [editMode, setEditMode] = useState(false)
    const [strategyId, setStrategyId] = useState<string | null>(null)

    // Mark dirty when strategy changes
    const markDirty = useCallback(() => {
        setIsDirty(true)
        setValidationResult(null)
    }, [])

    // Set entire strategy
    const setStrategy = useCallback((newStrategy: StrategyV2) => {
        setStrategyState(newStrategy)
        markDirty()
    }, [markDirty])

    // Update a single field
    const updateStrategyField = useCallback(<K extends keyof StrategyV2>(
        field: K,
        value: StrategyV2[K]
    ) => {
        setStrategyState(prev => ({ ...prev, [field]: value }))
        markDirty()
    }, [markDirty])

    // Load existing strategy for editing
    const loadStrategyAction = useCallback((s: StrategyV2, id?: string) => {
        setStrategyState(s)
        setEditMode(true)
        setStrategyId(id || null)
        setIsDirty(false)
        setValidationResult(null)
    }, [])

    // Reset to default
    const resetStrategy = useCallback(() => {
        setStrategyState(createDefaultStrategy())
        setEditMode(false)
        setStrategyId(null)
        setIsDirty(false)
        setValidationResult(null)
    }, [])

    // Entry conditions
    const addCondition = useCallback((condition?: Condition) => {
        const newCondition = condition || createDefaultCondition()
        setStrategyState(prev => ({
            ...prev,
            entry_conditions: [...prev.entry_conditions, newCondition],
        }))
        markDirty()
    }, [markDirty])

    const removeCondition = useCallback((conditionId: string) => {
        setStrategyState(prev => ({
            ...prev,
            entry_conditions: prev.entry_conditions.filter(c => c.id !== conditionId),
        }))
        markDirty()
    }, [markDirty])

    const updateCondition = useCallback((conditionId: string, updates: Partial<Condition>) => {
        setStrategyState(prev => ({
            ...prev,
            entry_conditions: prev.entry_conditions.map(c =>
                c.id === conditionId ? { ...c, ...updates } : c
            ),
        }))
        markDirty()
    }, [markDirty])

    const reorderConditions = useCallback((startIndex: number, endIndex: number) => {
        setStrategyState(prev => {
            const conditions = [...prev.entry_conditions]
            const [removed] = conditions.splice(startIndex, 1)
            conditions.splice(endIndex, 0, removed)
            return { ...prev, entry_conditions: conditions }
        })
        markDirty()
    }, [markDirty])

    const setEntryLogic = useCallback((logic: LogicType) => {
        setStrategyState(prev => ({ ...prev, entry_logic: logic }))
        markDirty()
    }, [markDirty])

    // Exit rules
    const addExitRule = useCallback((type: ExitRuleType) => {
        setStrategyState(prev => {
            const newRule = createDefaultExitRule(type)
            // Set priority to next available (computed from prev state to avoid stale closure)
            const maxPriority = prev.exit_rules.length > 0
                ? Math.max(...prev.exit_rules.map(r => r.priority))
                : 0
            const ruleWithPriority = { ...newRule, priority: maxPriority + 1 }

            return {
                ...prev,
                exit_rules: [...prev.exit_rules, ruleWithPriority],
            }
        })
        markDirty()
    }, [markDirty])

    const removeExitRule = useCallback((ruleId: string) => {
        setStrategyState(prev => ({
            ...prev,
            exit_rules: prev.exit_rules.filter(r => r.id !== ruleId),
        }))
        markDirty()
    }, [markDirty])

    const updateExitRule = useCallback((ruleId: string, updates: Partial<ExitRule>) => {
        setStrategyState(prev => ({
            ...prev,
            exit_rules: prev.exit_rules.map(r =>
                r.id === ruleId ? { ...r, ...updates } as ExitRule : r
            ),
        }))
        markDirty()
    }, [markDirty])

    const reorderExitRules = useCallback((startIndex: number, endIndex: number) => {
        setStrategyState(prev => {
            const rules = [...prev.exit_rules]
            const [removed] = rules.splice(startIndex, 1)
            rules.splice(endIndex, 0, removed)
            // Update priorities
            return {
                ...prev,
                exit_rules: rules.map((r, i) => ({ ...r, priority: i + 1 })),
            }
        })
        markDirty()
    }, [markDirty])

    const setExitLogic = useCallback((logic: LogicType) => {
        setStrategyState(prev => ({ ...prev, exit_logic: logic }))
        markDirty()
    }, [markDirty])

    // Risk config
    const updateRisk = useCallback((updates: Partial<RiskConfig>) => {
        setStrategyState(prev => ({
            ...prev,
            risk: { ...prev.risk, ...updates },
        }))
        markDirty()
    }, [markDirty])

    // API actions
    const validate = useCallback(async (): Promise<ValidationResult | null> => {
        setIsValidating(true)
        try {
            const result = await validateStrategy(strategy)
            setValidationResult(result)
            return result
        } catch (error) {
            console.error('Validation error:', error)
            const errorResult: ValidationResult = {
                valid: false,
                errors: ['Validation failed - please check your strategy'],
                warnings: [],
            }
            setValidationResult(errorResult)
            return errorResult
        } finally {
            setIsValidating(false)
        }
    }, [strategy])

    const save = useCallback(async (): Promise<string | null> => {
        setIsSaving(true)
        try {
            const result = await saveStrategy(strategy, strategyId || undefined)
            setStrategyId(result.strategy_id)
            setEditMode(true)
            setIsDirty(false)
            return result.strategy_id
        } catch (error) {
            console.error('Save error:', error)
            throw error
        } finally {
            setIsSaving(false)
        }
    }, [strategy, strategyId])

    const backtest = useCallback(async (): Promise<any | null> => {
        setIsBacktesting(true)
        try {
            const result = await backtestStrategy(strategy, 'quick')
            return result
        } catch (error) {
            console.error('Backtest error:', error)
            throw error
        } finally {
            setIsBacktesting(false)
        }
    }, [strategy])

    return useMemo(() => ({
        // State
        strategy,
        isDirty,
        isValidating,
        isSaving,
        isBacktesting,
        validationResult,
        editMode,
        strategyId,

        // Strategy actions
        setStrategy,
        updateStrategyField,
        loadStrategy: loadStrategyAction,
        resetStrategy,

        // Entry conditions
        addCondition,
        removeCondition,
        updateCondition,
        reorderConditions,
        setEntryLogic,

        // Exit rules
        addExitRule,
        removeExitRule,
        updateExitRule,
        reorderExitRules,
        setExitLogic,

        // Risk config
        updateRisk,

        // API actions
        validate,
        save,
        backtest,
    }), [
        strategy, isDirty, isValidating, isSaving, isBacktesting,
        validationResult, editMode, strategyId,
        setStrategy, updateStrategyField, loadStrategyAction, resetStrategy,
        addCondition, removeCondition, updateCondition, reorderConditions, setEntryLogic,
        addExitRule, removeExitRule, updateExitRule, reorderExitRules, setExitLogic,
        updateRisk, validate, save, backtest,
    ])
}
