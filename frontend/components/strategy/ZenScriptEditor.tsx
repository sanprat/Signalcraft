'use client'

import { useMemo, useState, useEffect } from 'react'
import {
    BarChart3,
    Check,
    ChevronRight,
    Search,
    Sparkles,
} from 'lucide-react'
import type { ComparisonOperator, Condition, MathOperand, StrategyV2 } from '@/lib/types/strategy'

interface ZenScriptEditorProps {
    strategy: StrategyV2
    onUpdateStrategy?: (strategy: Partial<StrategyV2>) => void
    onSubmitStrategy?: () => void
    isSubmitting?: boolean
}

type RuleTemplate = {
    label: string
    example: string
}

const RULE_TEMPLATES: RuleTemplate[] = [
    { label: 'Trend Breakout', example: 'Close > EMA(20) AND\nVolume > SMA(20)' },
    { label: 'Momentum Reversal', example: 'RSI(14) < 30 AND\nClose crosses_above SMA(50)' },
]

const OPERATOR_WORDS: Record<string, ComparisonOperator> = {
    '<': '<',
    '>': '>',
    '<=': '<=',
    '>=': '>=',
    '=': '==',
    '==': '==',
    '!=': '!=',
    crosses_above: 'crosses_above',
    crosses_below: 'crosses_below',
    'crosses above': 'crosses_above',
    'crosses below': 'crosses_below',
}

export function ZenScriptEditor({
    strategy,
    onUpdateStrategy,
    onSubmitStrategy,
    isSubmitting = false,
}: ZenScriptEditorProps) {
    // Generate initial text from conditions if we have them
    const initialQuery = useMemo(() => {
        if (!strategy.entry_conditions || strategy.entry_conditions.length === 0) return ''
        return strategy.entry_conditions.map(c => formatCondition(c)).join(' AND\n')
    }, [strategy.entry_conditions])

    const [query, setQuery] = useState(initialQuery)
    const [parseError, setParseError] = useState<string | null>(null)

    // Parse whenever query changes
    useEffect(() => {
        if (!query.trim()) {
            setParseError(null)
            if (onUpdateStrategy) onUpdateStrategy({ entry_conditions: [] })
            return
        }

        const parsed = parseStrategyQuery(query)
        if (parsed.length === 0 && query.trim().length > 0) {
            setParseError('Could not parse rules. Join multiple rules with AND.')
            return
        }

        setParseError(null)
        if (onUpdateStrategy) {
            onUpdateStrategy({ entry_conditions: parsed })
        }
    }, [query])

    const narrative = useMemo(() => generateStrategyNarrative(strategy), [strategy])

    return (
        <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                <div className="border-b border-slate-100 px-5 py-4 flex justify-between items-center">
                    <div>
                        <div className="flex items-center gap-2">
                            <Sparkles className="h-4 w-4 text-blue-600" />
                            <h3 className="text-sm font-bold text-slate-800">Entry Criteria (Screener Style)</h3>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-slate-500">
                            Write your entry conditions in natural language. Use the Config, Exit, and Risk tabs to finish setup.
                        </p>
                    </div>
                </div>

                <div className="p-5">
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                        <div className="mb-3 flex items-center justify-between gap-2">
                            <span className="text-xs font-bold uppercase tracking-wide text-slate-500">Query</span>
                        </div>
                        <div className="relative">
                            <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
                            <textarea
                                value={query}
                                onChange={(event) => setQuery(event.target.value)}
                                placeholder={`RSI(14) < 40 AND\nClose > EMA(20) AND\nVolume > SMA(20)`}
                                spellCheck={false}
                                className="min-h-[250px] w-full resize-y rounded-lg border border-slate-300 bg-white py-3 pl-9 pr-4 font-mono text-sm font-medium leading-7 text-slate-800 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                            />
                        </div>
                    </div>

                    {parseError ? (
                        <div className="mt-3 rounded-lg bg-red-50 border border-red-100 px-4 py-3 text-xs font-medium leading-5 text-red-700 flex items-start gap-2">
                            <svg className="w-4 h-4 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                            {parseError}
                        </div>
                    ) : (
                        strategy.entry_conditions.length > 0 && (
                            <div className="mt-3 rounded-lg bg-emerald-50 border border-emerald-100 px-4 py-3 text-xs font-medium leading-5 text-emerald-700 flex items-center gap-2">
                                <Check className="w-4 h-4 text-emerald-600" />
                                Successfully parsed {strategy.entry_conditions.length} condition(s)
                            </div>
                        )
                    )}

                    <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50/50 p-4">
                        <div className="text-[11px] font-bold uppercase tracking-wide text-blue-700 mb-2">
                            Quick Snippets
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                            {RULE_TEMPLATES.map(template => (
                                <div key={template.label} className="text-xs bg-white border border-blue-100 rounded p-3 cursor-pointer hover:border-blue-300 transition-colors" onClick={() => {
                                    const connector = query.trim() ? (query.trim().endsWith('AND') ? '\n' : '\nAND\n') : '';
                                    setQuery(query + connector + template.example);
                                }}>
                                    <span className="block font-semibold text-slate-600 mb-2">{template.label}</span>
                                    <pre className="font-mono text-blue-800 text-[11px] leading-relaxed overflow-x-auto">{template.example}</pre>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                <div className="border-b border-slate-100 px-5 py-4">
                    <div className="flex items-center justify-between">
                        <h3 className="text-sm font-bold text-slate-800">Strategy Brief</h3>
                    </div>
                </div>

                <div className="space-y-3 p-5">
                    {narrative.map((line, index) => (
                        <div key={`${line}-${index}`} className="flex gap-3 text-sm leading-6">
                            <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-blue-500" />
                            <span className="text-slate-700 font-medium">{line}</span>
                        </div>
                    ))}

                    <button
                        type="button"
                        onClick={onSubmitStrategy}
                        disabled={isSubmitting || !!parseError || strategy.entry_conditions.length === 0}
                        className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3.5 text-sm font-bold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300 shadow-sm"
                    >
                        {isSubmitting ? (
                            <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                        ) : (
                            <BarChart3 className="h-4 w-4" />
                        )}
                        {isSubmitting ? 'Submitting to Python...' : 'Run Backtest'}
                    </button>
                </div>
            </div>
        </div>
    )
}

function parseStrategyQuery(query: string): Condition[] {
    const conditions = query
        .split(/\s+AND\s+|\n+/i)
        .map(part => parseConditionQuery(part))
        .filter((condition): condition is Omit<Condition, 'id'> => Boolean(condition));
        
    return conditions.map((c, idx) => ({
        ...c,
        id: `cond_${Date.now()}_${idx}_${Math.random().toString(36).slice(2, 11)}`
    }));
}

function parseConditionQuery(query: string): Omit<Condition, 'id'> | null {
    const normalized = query.trim().replace(/\s+/g, ' ').replace(/^\/\/.*$/, '');
    if (!normalized) return null;

    const operatorMatch = Object.keys(OPERATOR_WORDS)
        .sort((a, b) => b.length - a.length)
        .find(operator => normalized.toLowerCase().includes(` ${operator} `) || normalized.includes(operator));

    if (!operatorMatch) return null;

    const operator = OPERATOR_WORDS[operatorMatch];
    const parts = normalized.split(new RegExp(`\\s*${escapeRegExp(operatorMatch)}\\s*`, 'i'));
    if (parts.length !== 2) return null;

    const left = parseOperand(parts[0]);
    const right = parseOperand(parts[1]);
    if (!left || !right) return null;

    return { left, operator, right };
}

function parseOperand(value: string): MathOperand | null {
    const token = value.trim();
    if (!token) return null;

    const numeric = Number(token);
    if (!Number.isNaN(numeric)) {
        return { type: 'value', value: numeric };
    }

    const priceField = token.toLowerCase();
    if (['close', 'open', 'high', 'low', 'volume', 'ohlc', 'hl2', 'hlc3', 'hlcc4', 'price'].includes(priceField)) {
        return { type: 'price', field: priceField === 'price' ? 'close' : priceField as any };
    }

    const indicatorMatch = token.match(/^([a-z_]+)\s*\(([^)]*)\)$/i);
    if (indicatorMatch) {
        const params = indicatorMatch[2]
            .split(',')
            .map(param => param.trim())
            .filter(Boolean)
            .map(param => {
                const numberValue = Number(param);
                return Number.isNaN(numberValue) ? param : numberValue;
            });

        return {
            type: 'indicator',
            name: indicatorMatch[1].toUpperCase(),
            params,
        };
    }

    const compactIndicator = token.match(/^([a-z_]+)\s+(\d+(?:\.\d+)?)$/i);
    if (compactIndicator) {
        return {
            type: 'indicator',
            name: compactIndicator[1].toUpperCase(),
            params: [Number(compactIndicator[2])],
        };
    }

    return {
        type: 'indicator',
        name: token.toUpperCase(),
        params: [],
    };
}

function escapeRegExp(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function generateStrategyNarrative(strategy: StrategyV2): string[] {
    const symbols = strategy.symbols?.length ? strategy.symbols.join(', ') : 'selected symbols'
    const conditions = strategy.entry_conditions?.length || 0
    const exits = strategy.exit_rules?.length || 0
    const lines = [
        `Trade ${symbols} on ${strategy.timeframe || '15m'} candles.`,
        `Enter when ${strategy.entry_logic === 'ALL' ? 'all' : 'any'} of the ${conditions || 'configured'} entry rules match.`,
        exits > 0
            ? `Exit on ${strategy.exit_logic === 'ALL' ? 'all' : 'any'} of ${exits} exit rules, with ${strategy.risk?.quantity || 1} quantity per trade.`
            : `Add at least one exit rule before backtesting.`,
    ]

    if (strategy.backtest_from && strategy.backtest_to) {
        lines.push(`Backtest window is ${strategy.backtest_from} to ${strategy.backtest_to}.`)
    }

    return lines
}

function formatCondition(condition: Condition): string {
    return `${formatConditionSide(condition.left)} ${formatOperator(condition.operator)} ${formatConditionSide(condition.right)}`
}

function formatConditionSide(side: any): string {
    if (!side) return 'N/A'
    if (typeof side === 'number') return side.toString()
    if (typeof side === 'string') return side
    if (side.type === 'value') return side.value.toString()
    if (side.type === 'price') return side.field.toUpperCase()
    if (side.type === 'indicator') {
        const params = side.params?.length ? `(${side.params.join(', ')})` : ''
        return `${side.name}${params}`
    }
    if (side.type === 'math') {
        return `(${formatConditionSide(side.left)} ${side.operator} ${formatConditionSide(side.right)})`
    }
    return 'N/A'
}

function formatOperator(op: string): string {
    const opMap: Record<string, string> = {
        '<': '<',
        '>': '>',
        '<=': '<=',
        '>=': '>=',
        '==': '=',
        '!=': '!=',
        crosses_above: 'crosses above',
        crosses_below: 'crosses below',
    }
    return opMap[op] || op
}
