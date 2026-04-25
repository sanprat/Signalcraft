'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useStrategy } from '@/hooks/useStrategy'
import { loadStrategy } from '@/lib/api/strategy'
import { BackButton } from '@/components/BackButton'
import { StrategyConfig } from '@/components/strategy/StrategyConfig'
import { ExitBuilder } from '@/components/strategy/ExitBuilder'
import { RiskPanel } from '@/components/strategy/RiskPanel'
import { EntryBuilder } from '@/components/strategy/EntryBuilder'
import { ZenScriptQuery } from '@/components/strategy/ZenScriptQuery'
import { ValidationResults } from '@/components/strategy/ValidationResults'
import { isValidDateRange, isValidDateString } from '@/lib/date'
import type {
    AssetType,
    ConfigNLPResponse,
    EntryNLPResponse,
    ExitNLPResponse,
    IndexType,
    NLPParseResponse,
    OptionType,
    RiskNLPResponse,
    StrikeType,
    TimeframeType,
} from '@/lib/types/strategy'

type Section = 'config' | 'entry' | 'exit' | 'risk'
const SECTIONS: { id: Section; label: string; icon: string }[] = [
    { id: 'entry', label: 'ZenScript', icon: '✨' },
    { id: 'config', label: 'Config', icon: '⚙️' },
    { id: 'exit', label: 'Exit', icon: '🚪' },
    { id: 'risk', label: 'Risk', icon: '🛡️' },
]

const T = {
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF', blueMid: '#BFDBFE',
    green: '#059669', greenLight: '#ECFDF5', greenMid: '#A7F3D0',
    red: '#DC2626', redLight: '#FEF2F2', redMid: '#FECACA',
    amber: '#D97706', amberLight: '#FFFBEB',
    text: '#0F172A', textMid: '#475569', textMuted: '#94A3B8', pill: '#F1F5F9',
    border: '#E2E8F0', surface: '#FFFFFF', bg: '#F8FAFC', surfaceHover: '#F1F5F9'
}

function StrategyBuilderContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const [activeSection, setActiveSection] = useState<Section>('entry')
    const [showPreview, setShowPreview] = useState(true)
    const [showValidation, setShowValidation] = useState(false)
    const [notification, setNotification] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null)

    const {
        strategy,
        isDirty,
        isValidating,
        isSaving,
        isBacktesting,
        validationResult,
        editMode,
        strategyId,
        setStrategy,
        updateStrategyField,
        loadStrategy: loadStrategyIntoHook,
        resetStrategy,
        addCondition,
        removeCondition,
        updateCondition,
        reorderConditions,
        setEntryLogic,
        addExitRule,
        removeExitRule,
        updateExitRule,
        reorderExitRules,
        setExitLogic,
        updateRisk,
        validate,
        save,
        backtest,
    } = useStrategy()

    // Load strategy if editing
    useEffect(() => {
        const editId = searchParams.get('edit')
        if (editId) {
            loadStrategy(editId)
                .then(data => {
                    loadStrategyIntoHook(data.strategy, data.strategy_id)
                    showNotification('success', `Loaded strategy: ${data.strategy.name}`)
                })
                .catch(err => {
                    console.error('Failed to load strategy:', err)
                    showNotification('error', 'Failed to load strategy')
                })
        }
    }, [searchParams])

    // Set default date range
    useEffect(() => {
        if (!strategy.backtest_from || !strategy.backtest_to) {
            const today = new Date()
            const yearAgo = new Date(today.getTime() - 365 * 24 * 60 * 60 * 1000)
            updateStrategyField('backtest_from', yearAgo.toISOString().split('T')[0])
            updateStrategyField('backtest_to', today.toISOString().split('T')[0])
        }
    }, [])

    const showNotification = (type: 'success' | 'error' | 'info', message: string) => {
        setNotification({ type, message })
        setTimeout(() => setNotification(null), 4000)
    }

    const handleEntryNLPApply = (result: NLPParseResponse) => {
        const data = result as EntryNLPResponse
        setStrategy({ ...strategy, entry_conditions: data.conditions } as any)
    }

    const handleConfigNLPApply = (result: NLPParseResponse) => {
        const data = result as ConfigNLPResponse
        setStrategy({ ...strategy, ...data.config } as any)
    }

    const handleExitNLPApply = (result: NLPParseResponse) => {
        const data = result as ExitNLPResponse
        setStrategy({
            ...strategy,
            exit_rules: data.exit_rules,
            exit_logic: data.exit_logic ?? strategy.exit_logic,
        } as any)
    }

    const handleRiskNLPApply = (result: NLPParseResponse) => {
        const data = result as RiskNLPResponse
        setStrategy({ ...strategy, risk: data.risk } as any)
    }

    const ensureValidBacktestDates = (): boolean => {
        if (!isValidDateString(strategy.backtest_from) || !isValidDateString(strategy.backtest_to)) {
            showNotification('error', 'Please enter a complete backtest date range in YYYY-MM-DD format')
            setActiveSection('config')
            return false
        }

        if (!isValidDateRange(strategy.backtest_from, strategy.backtest_to)) {
            showNotification('error', 'Backtest start date must be on or before the end date')
            setActiveSection('config')
            return false
        }

        return true
    }

    const checkDuplicateStrategyName = async (): Promise<boolean> => {
        if (editMode && strategyId) return false
        try {
            const { listStrategies } = await import('@/lib/api/strategy')
            const existing = await listStrategies()
            const duplicate = existing.find(s => s.name.toLowerCase() === strategy.name.toLowerCase())
            if (duplicate) {
                showNotification('error', `A strategy with the name '${strategy.name}' already exists.`)
                setActiveSection('config')
                return true
            }
        } catch (err) {
            console.warn('Could not check for duplicate strategy names:', err)
        }
        return false
    }

    const handleValidate = async () => {
        setShowValidation(true)
        try {
            const result = await validate()
            if (result?.valid) {
                showNotification('success', 'Strategy is valid!')
            } else {
                showNotification('error', 'Strategy has validation errors')
            }
        } catch (err: any) {
            console.error('Validation error:', err)
            showNotification('error', err.message || 'Validation failed')
        }
    }

    const handleSave = async () => {
        if (!strategy.name.trim()) {
            showNotification('error', 'Please enter a strategy name')
            setActiveSection('config')
            return
        }
        if (strategy.symbols.length === 0) {
            showNotification('error', 'Please select at least one symbol')
            setActiveSection('config')
            return
        }
        if (strategy.entry_conditions.length === 0) {
            showNotification('error', 'Please add at least one entry condition')
            setActiveSection('entry')
            return
        }
        if (strategy.exit_rules.length === 0) {
            showNotification('error', 'Please add at least one exit rule')
            setActiveSection('exit')
            return
        }
        if (!ensureValidBacktestDates()) {
            return
        }

        const isDuplicate = await checkDuplicateStrategyName()
        if (isDuplicate) return

        try {
            const id = await save()
            showNotification('success', `Strategy saved! ID: ${id}`)
        } catch (err: any) {
            showNotification('error', err.message || 'Failed to save strategy')
        }
    }

    const handleBacktest = async () => {
        if (!strategy.name.trim()) {
            showNotification('error', 'Please enter a strategy name')
            return
        }
        if (!ensureValidBacktestDates()) {
            return
        }

        const isDuplicate = await checkDuplicateStrategyName()
        if (isDuplicate) return

        try {
            // First validate
            const result = await validate()
            if (!result?.valid) {
                setShowValidation(true)
                showNotification('error', 'Fix validation errors before backtesting')
                return
            }

            // Save first if dirty
            if (isDirty || !strategyId) {
                const id = await save()
                showNotification('success', `Strategy saved! Running backtest...`)
            }

            // Run backtest
            const btResult = await backtest()
            if (btResult && btResult.backtest_id) {
                router.push(`/backtest/${btResult.backtest_id}`)
            } else {
                showNotification('info', 'Backtest completed! Check results.')
            }
        } catch (err: any) {
            showNotification('error', err.message || 'Backtest failed')
        }
    }

    const renderSection = () => {
        switch (activeSection) {
            case 'config':
                return (
                    <div className="space-y-6">
                        <ZenScriptQuery
                            section="config"
                            title="ZenScript NLP Query"
                            description="Describe strategy setup in natural English. This replaces the current Config section with the parsed strategy metadata."
                            placeholder="e.g., Create a strategy named 'Nifty Momentum' for RELIANCE and TCS on 15 minute candles from 2025-01-01 to 2025-03-31."
                            successLabel="config values"
                            onApply={handleConfigNLPApply}
                        />
                        <StrategyConfig
                            name={strategy.name}
                            symbols={strategy.symbols}
                            assetType={strategy.asset_type}
                            index={strategy.index}
                            optionType={strategy.option_type}
                            strikeType={strategy.strike_type}
                            timeframe={strategy.timeframe}
                            backtestFrom={strategy.backtest_from}
                            backtestTo={strategy.backtest_to}
                            onNameChange={(name) => updateStrategyField('name', name)}
                            onSymbolsChange={(symbols) => updateStrategyField('symbols', symbols)}
                            onAssetTypeChange={(asset_type) => updateStrategyField('asset_type', asset_type)}
                            onIndexChange={(index) => updateStrategyField('index', index)}
                            onOptionTypeChange={(option_type) => updateStrategyField('option_type', option_type)}
                            onStrikeTypeChange={(strike_type) => updateStrategyField('strike_type', strike_type)}
                            onTimeframeChange={(timeframe) => updateStrategyField('timeframe', timeframe)}
                            onDateRangeChange={(backtest_from, backtest_to) => {
                                updateStrategyField('backtest_from', backtest_from)
                                updateStrategyField('backtest_to', backtest_to)
                            }}
                        />
                    </div>
                )

            case 'entry':
                return (
                    <div className="space-y-6">
                        <ZenScriptQuery
                            section="entry"
                            title="ZenScript NLP Query"
                            description="Type your entry logic in natural English. This replaces the current Entry Conditions with parsed visual blocks."
                            placeholder="e.g., Buy when the 14-period RSI drops below 30 and price crosses above the 200 SMA."
                            successLabel="entry conditions"
                            onApply={handleEntryNLPApply}
                        />
                        <EntryBuilder
                            conditions={strategy.entry_conditions}
                            entryLogic={strategy.entry_logic}
                            onAddCondition={addCondition}
                            onRemoveCondition={removeCondition}
                            onUpdateCondition={updateCondition}
                            onReorderConditions={reorderConditions}
                            onSetEntryLogic={setEntryLogic}
                        />
                    </div>
                )

            case 'exit':
                return (
                    <div className="space-y-6">
                        <ZenScriptQuery
                            section="exit"
                            title="ZenScript NLP Query"
                            description="Describe exit logic in natural English. This replaces the current Exit section with parsed stop, target, trailing, time, or indicator exits."
                            placeholder="e.g., Exit with 2% stop loss, 5% target, trailing stop 1.5% after 3% profit, and RSI crosses below 60."
                            successLabel="exit rules"
                            onApply={handleExitNLPApply}
                        />
                        <ExitBuilder
                            exitRules={strategy.exit_rules}
                            exitLogic={strategy.exit_logic}
                            onAddExitRule={addExitRule}
                            onRemoveExitRule={removeExitRule}
                            onUpdateExitRule={updateExitRule}
                            onReorderExitRules={reorderExitRules}
                            onSetExitLogic={setExitLogic}
                        />
                    </div>
                )

            case 'risk':
                return (
                    <div className="space-y-6">
                        <ZenScriptQuery
                            section="risk"
                            title="ZenScript NLP Query"
                            description="Describe risk settings in natural English. This replaces the current Risk section with parsed position sizing and guardrails."
                            placeholder="e.g., Max 3 trades per day, daily loss 5000, quantity 10, max open positions 2, partial exit 50%, enable re-entry."
                            successLabel="risk settings"
                            onApply={handleRiskNLPApply}
                        />
                        <RiskPanel
                            risk={strategy.risk}
                            assetType={strategy.asset_type}
                            onUpdate={updateRisk}
                        />
                    </div>
                )

            default:
                return null
        }
    }

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <div className="bg-white border-b border-slate-200 sticky top-0 z-30">
                <div className="max-w-7xl mx-auto px-4 py-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <BackButton defaultBack="/dashboard" />
                            <div>
                                <h1 className="text-lg font-bold text-slate-800">
                                    {editMode ? 'Edit Strategy' : 'Build Strategy'}
                                </h1>
                                {isDirty && (
                                    <span className="text-xs text-amber-500">Unsaved changes</span>
                                )}
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setShowPreview(!showPreview)}
                                className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                                    showPreview
                                        ? 'bg-slate-800 text-white'
                                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                }`}
                            >
                                📋 Preview
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="max-w-7xl mx-auto px-4 py-6">
                <div className={`grid gap-6 ${showPreview ? 'grid-cols-1 lg:grid-cols-5' : 'grid-cols-1'}`}>
                    {/* Main Editor */}
                    <div className={showPreview ? 'lg:col-span-3' : 'col-span-1'}>
                        {/* Section Tabs */}
                        <div className="flex gap-1 mb-4 bg-slate-100 p-1 rounded-lg overflow-x-auto">
                            {SECTIONS.map(section => (
                                <button
                                    key={section.id}
                                    onClick={() => setActiveSection(section.id)}
                                    className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${
                                        activeSection === section.id
                                            ? 'bg-white text-blue-600 shadow-sm'
                                            : 'text-slate-600 hover:text-slate-800'
                                    }`}
                                >
                                    <span>{section.icon}</span>
                                    <span>{section.label}</span>
                                </button>
                            ))}
                        </div>

                        {/* Section Content */}
                        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
                            {/* Section Header */}
                            <div className="px-5 py-4 border-b border-slate-100">
                                <h2 className="text-lg font-semibold text-slate-800">
                                    {SECTIONS.find(s => s.id === activeSection)?.label} Configuration
                                </h2>
                            </div>

                            {/* Section Body */}
                            <div className="p-5">
                                {renderSection()}
                            </div>
                        </div>

                        {/* Validation Results */}
                        {showValidation && (
                            <div className="mt-4">
                                <ValidationResults
                                    result={validationResult}
                                    isValidating={isValidating}
                                />
                            </div>
                        )}

                        {/* Action Buttons */}
                        <div className="mt-6 flex flex-wrap gap-3">
                            <button
                                onClick={handleValidate}
                                disabled={isValidating}
                                style={{ 
                                    background: T.bg, color: T.textMid, border: `1px solid ${T.border}`,
                                    borderRadius: 10, padding: '10px 20px', fontSize: 13, fontWeight: 700,
                                    cursor: isValidating ? 'not-allowed' : 'pointer', transition: 'all 0.2s',
                                    display: 'flex', alignItems: 'center', gap: 8, opacity: isValidating ? 0.6 : 1,
                                }}
                            >
                                {isValidating ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-slate-500 border-t-transparent rounded-full animate-spin" />
                                        Validating...
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                        Validate
                                    </>
                                )}
                            </button>

                            <button
                                onClick={handleSave}
                                disabled={isSaving}
                                style={{ 
                                    background: T.blueLight, color: T.blue, border: `1px solid ${T.blueMid}`,
                                    borderRadius: 10, padding: '10px 20px', fontSize: 13, fontWeight: 700,
                                    cursor: isSaving ? 'not-allowed' : 'pointer', transition: 'all 0.2s',
                                    display: 'flex', alignItems: 'center', gap: 8, opacity: isSaving ? 0.6 : 1,
                                }}
                            >
                                {isSaving ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                                        Saving...
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                                        </svg>
                                        Save Strategy
                                    </>
                                )}
                            </button>

                            <button
                                onClick={handleBacktest}
                                disabled={isBacktesting}
                                style={{ 
                                    background: T.green, color: 'white', border: `1px solid ${T.green}`,
                                    borderRadius: 10, padding: '10px 24px', fontSize: 14, fontWeight: 800,
                                    cursor: isBacktesting ? 'not-allowed' : 'pointer', transition: 'all 0.2s',
                                    display: 'flex', alignItems: 'center', gap: 8, opacity: isBacktesting ? 0.6 : 1,
                                    boxShadow: '0 4px 12px rgba(5, 150, 105, 0.25)'
                                }}
                            >
                                {isBacktesting ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                        Running Backtest...
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                        </svg>
                                        Run Backtest
                                    </>
                                )}
                            </button>
                        </div>
                    </div>

                    {/* Preview Sidebar */}
                    {showPreview && (
                        <div className="lg:col-span-2">
                            <div className="sticky top-24">
                                {/* Quick Stats */}
                                <div className="mt-4 bg-white rounded-xl border border-slate-200 p-4">
                                    <h3 className="text-sm font-semibold text-slate-700 mb-3">Quick Stats</h3>
                                    <div className="space-y-2 text-sm">
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">Conditions:</span>
                                            <span className="font-semibold text-slate-700">
                                                {(strategy.entry_conditions || []).length}
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">Exit Rules:</span>
                                            <span className="font-semibold text-slate-700">
                                                {(strategy.exit_rules || []).length}
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">Symbols:</span>
                                            <span className="font-semibold text-slate-700">
                                                {(strategy.symbols || []).length}
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">Timeframe:</span>
                                            <span className="font-semibold text-slate-700">
                                                {strategy.timeframe}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Toast Notification */}
            {notification && (
                <div className={`fixed bottom-4 right-4 px-4 py-3 rounded-lg shadow-lg z-50 flex items-center gap-2 animate-slide-up ${
                    notification.type === 'success'
                        ? 'bg-green-50 text-green-800 border border-green-200'
                        : notification.type === 'error'
                        ? 'bg-red-50 text-red-800 border border-red-200'
                        : 'bg-blue-50 text-blue-800 border border-blue-200'
                }`}>
                    {notification.type === 'success' ? (
                        <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    ) : notification.type === 'error' ? (
                        <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    ) : (
                        <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    )}
                    <span className="text-sm font-medium">{notification.message}</span>
                    <button
                        onClick={() => setNotification(null)}
                        className="ml-2 text-slate-400 hover:text-slate-600"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            )}
        </div>
    )
}

export default function NewStrategyPage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <div className="text-center">
                    <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-slate-500">Loading strategy builder...</p>
                </div>
            </div>
        }>
            <StrategyBuilderContent />
        </Suspense>
    )
}
