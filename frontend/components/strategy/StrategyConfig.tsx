'use client'

import { useState } from 'react'
import type { AssetType, IndexType, OptionType, StrikeType, TimeframeType } from '@/lib/types/strategy'
import { SymbolSelector } from './SymbolSelector'
import { TimeframeSelector } from './TimeframeSelector'
import { DateRangePicker } from './DateRangePicker'

interface StrategyConfigProps {
    name: string
    symbols: string[]
    assetType: AssetType
    index?: IndexType
    optionType?: OptionType
    strikeType?: StrikeType
    timeframe: TimeframeType
    backtestFrom?: string
    backtestTo?: string
    onNameChange: (name: string) => void
    onSymbolsChange: (symbols: string[]) => void
    onAssetTypeChange: (assetType: AssetType) => void
    onIndexChange: (index: IndexType) => void
    onOptionTypeChange: (optionType: OptionType) => void
    onStrikeTypeChange: (strikeType: StrikeType) => void
    onTimeframeChange: (timeframe: TimeframeType) => void
    onDateRangeChange: (from: string, to: string) => void
}

export function StrategyConfig({
    name,
    symbols,
    assetType,
    index,
    optionType,
    strikeType,
    timeframe,
    backtestFrom,
    backtestTo,
    onNameChange,
    onSymbolsChange,
    onAssetTypeChange,
    onIndexChange,
    onOptionTypeChange,
    onStrikeTypeChange,
    onTimeframeChange,
    onDateRangeChange,
}: StrategyConfigProps) {
    return (
        <div className="space-y-6">
            {/* Strategy Name */}
            <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Strategy Name
                </label>
                <input
                    type="text"
                    value={name}
                    onChange={(e) => onNameChange(e.target.value)}
                    placeholder="e.g., EMA Crossover Breakout"
                    className="w-full px-4 py-3 text-base border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
            </div>

            {/* Asset Type */}
            <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Asset Type
                </label>
                <div className="flex gap-3">
                    <button
                        type="button"
                        onClick={() => onAssetTypeChange('EQUITY')}
                        className={`flex-1 px-4 py-3 rounded-lg border-2 font-medium transition-all ${
                            assetType === 'EQUITY'
                                ? 'border-blue-600 bg-blue-50 text-blue-700'
                                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                        }`}
                    >
                        <div className="text-lg mb-1">📈</div>
                        <div>Equities</div>
                        <div className="text-xs font-normal opacity-75">Nifty50 Stocks</div>
                    </button>
                    <button
                        type="button"
                        disabled
                        className="flex-1 px-4 py-3 rounded-lg border-2 font-medium transition-all border-slate-100 bg-slate-50 text-slate-400 cursor-not-allowed"
                    >
                        <div className="text-lg mb-1">⚡</div>
                        <div>Futures & Options</div>
                        <div className="text-xs font-normal opacity-75">Coming Soon</div>
                    </button>
                </div>
            </div>

            {/* Symbols / Index */}
            {/* Always show EQUITY UI - F&O is disabled */}
            <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Trading Symbols
                </label>
                <SymbolSelector
                    selectedSymbols={symbols}
                    onChange={onSymbolsChange}
                    maxSymbols={50}
                />
            </div>

            {/* Timeframe */}
            <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Candle Timeframe
                </label>
                <TimeframeSelector
                    value={timeframe}
                    onChange={onTimeframeChange}
                    assetType={assetType}
                />
            </div>

            {/* Date Range */}
            <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Backtest Period
                </label>
                <DateRangePicker
                    startDate={backtestFrom || ''}
                    endDate={backtestTo || ''}
                    onChange={onDateRangeChange}
                />
            </div>
        </div>
    )
}
