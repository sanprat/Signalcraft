'use client'

import type { RiskConfig, AssetType } from '@/lib/types/strategy'

interface RiskPanelProps {
    risk: RiskConfig
    assetType: AssetType
    onUpdate: (updates: Partial<RiskConfig>) => void
}

export function RiskPanel({ risk, assetType, onUpdate }: RiskPanelProps) {
    const hasTradeLimit = risk.max_trades_per_day > 0
    const hasDailyLossCap = risk.max_loss_per_day > 0

    return (
        <div className="space-y-4">
            {/* Header */}
            <div>
                <h3 className="text-base font-semibold text-slate-800">Risk Management</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                    Configure position sizing and risk limits
                </p>
            </div>

            {/* Risk Inputs */}
            <div className="grid grid-cols-2 gap-4">
                {/* Max Trades Per Day */}
                <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">
                        Max Trades Per Day
                    </label>
                    <div className="space-y-2">
                        <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-1">
                            <button
                                type="button"
                                onClick={() => onUpdate({ max_trades_per_day: 0 })}
                                className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                                    !hasTradeLimit
                                        ? "bg-white text-slate-900 shadow-sm"
                                        : "text-slate-500 hover:text-slate-700"
                                }`}
                            >
                                No Limit
                            </button>
                            <button
                                type="button"
                                onClick={() => onUpdate({ max_trades_per_day: hasTradeLimit ? risk.max_trades_per_day : 1 })}
                                className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                                    hasTradeLimit
                                        ? "bg-white text-slate-900 shadow-sm"
                                        : "text-slate-500 hover:text-slate-700"
                                }`}
                            >
                                Set Limit
                            </button>
                        </div>
                        {hasTradeLimit ? (
                            <input
                                type="number"
                                min="1"
                                max="50"
                                value={risk.max_trades_per_day}
                                onChange={(e) =>
                                    onUpdate({ max_trades_per_day: Math.min(Math.max(parseInt(e.target.value) || 1, 1), 50) })
                                }
                                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            />
                        ) : (
                            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
                                No daily trade cap
                            </div>
                        )}
                    </div>
                </div>

                {/* Max Daily Loss */}
                <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">
                        Max Daily Loss (₹)
                    </label>
                    <div className="space-y-2">
                        <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-1">
                            <button
                                type="button"
                                onClick={() => onUpdate({ max_loss_per_day: 0 })}
                                className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                                    !hasDailyLossCap
                                        ? "bg-white text-slate-900 shadow-sm"
                                        : "text-slate-500 hover:text-slate-700"
                                }`}
                            >
                                No Cap
                            </button>
                            <button
                                type="button"
                                onClick={() => onUpdate({ max_loss_per_day: hasDailyLossCap ? risk.max_loss_per_day : 1000 })}
                                className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                                    hasDailyLossCap
                                        ? "bg-white text-slate-900 shadow-sm"
                                        : "text-slate-500 hover:text-slate-700"
                                }`}
                            >
                                Set Cap
                            </button>
                        </div>
                        {hasDailyLossCap ? (
                            <input
                                type="number"
                                min="0"
                                max="1000000"
                                step="100"
                                value={risk.max_loss_per_day}
                                onChange={(e) => {
                                    const val = parseFloat(e.target.value) || 0
                                    const clampedVal = Math.min(Math.max(val, 0), 1000000)
                                    onUpdate({ max_loss_per_day: clampedVal })
                                }}
                                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
                            />
                        ) : (
                            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
                                No daily loss cap
                            </div>
                        )}
                    </div>
                </div>

                {/* Quantity */}
                <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">
                        {assetType === 'EQUITY' ? 'Quantity (Shares)' : 'Quantity (Lots)'}
                    </label>
                    <input
                        type="number"
                        min="1"
                        max="10000"
                        value={risk.quantity}
                        onChange={(e) => {
                            const val = parseInt(e.target.value) || 1
                            // Clamp value to bounds
                            const clampedVal = Math.min(Math.max(val, 1), 10000)
                            onUpdate({ quantity: clampedVal })
                        }}
                        className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>

                {/* Max Concurrent Trades */}
                <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">
                        Max Open Positions
                    </label>
                    <input
                        type="number"
                        min="1"
                        max="10"
                        value={risk.max_concurrent_trades}
                        onChange={(e) => onUpdate({ max_concurrent_trades: parseInt(e.target.value) || 1 })}
                        className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>

                {/* Partial Exit */}
                <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">
                        Partial Exit at Target (%)
                    </label>
                    <input
                        type="number"
                        min="0"
                        max="100"
                        placeholder="Optional"
                        value={risk.partial_exit_pct ?? ''}
                        onChange={(e) => {
                            const value = e.target.value ? parseFloat(e.target.value) : undefined
                            onUpdate({ partial_exit_pct: value })
                        }}
                        className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    />
                </div>
            </div>

            {/* Re-entry Toggle */}
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                <div>
                    <div className="text-sm font-medium text-slate-700">Re-entry After Stop Loss</div>
                    <div className="text-xs text-slate-400">
                        Allow entering a new position after being stopped out
                    </div>
                </div>
                <button
                    type="button"
                    onClick={() => onUpdate({ reentry_after_sl: !risk.reentry_after_sl })}
                    className={`relative w-11 h-6 rounded-full transition-colors ${
                        risk.reentry_after_sl ? 'bg-blue-600' : 'bg-slate-300'
                    }`}
                >
                    <span
                        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform shadow ${
                            risk.reentry_after_sl ? 'translate-x-5' : ''
                        }`}
                    />
                </button>
            </div>

            {/* Risk Summary */}
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-start gap-2">
                    <svg className="w-4 h-4 text-amber-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div className="text-xs text-amber-700">
                        <strong>Risk Summary:</strong>{" "}
                        {hasTradeLimit
                            ? `Max ${risk.max_trades_per_day} trades/day`
                            : "No daily trade cap"}
                        {hasDailyLossCap
                            ? ` with up to ₹${risk.max_loss_per_day.toLocaleString()} daily loss limit.`
                            : ' with no daily loss cap.'}
                        {risk.reentry_after_sl && ' Re-entry after SL is enabled.'}
                    </div>
                </div>
            </div>
        </div>
    )
}
