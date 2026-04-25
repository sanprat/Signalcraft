'use client'

import { useMemo, useState, useEffect } from 'react'
import {
    BarChart3,
    Check,
    ChevronRight,
    Copy,
    Search,
    Sparkles,
} from 'lucide-react'
import type { ComparisonOperator, Condition, MathOperand, StrategyV2, ExitRule, RiskConfig } from '@/lib/types/strategy'

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
    { label: 'Full Basic Strategy', example: 'STRATEGY "Trend Follower" {\n    SYMBOLS: RELIANCE\n    TIMEFRAME: 15m\n    DATE_RANGE: 2024-04-25 to 2026-04-25\n\n    ENTRY ALL {\n        RSI(14) < 40\n        Close > EMA(20)\n    }\n\n    EXIT ANY {\n        STOPLOSS 2%\n        TARGET 5%\n    }\n\n    RISK {\n        QUANTITY: 100\n    }\n}' },
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
    // Keep local text state
    const [query, setQuery] = useState('')
    const [parseError, setParseError] = useState<string | null>(null)
    const [parsedStrategy, setParsedStrategy] = useState<Partial<StrategyV2> | null>(null)

    // On mount or when strategy changes externally (not from this component's own updates)
    // we could update the text. But to avoid resetting cursor position while typing, 
    // we only set it initially or when it's completely empty.
    useEffect(() => {
        if (!query.trim()) {
            setQuery(generateZenScript(strategy))
        }
    }, [])

    // Parse whenever query changes
    useEffect(() => {
        if (!query.trim()) {
            setParseError(null)
            return
        }

        try {
            const parsed = parseFullZenScript(query)
            setParsedStrategy(parsed)
            setParseError(null)
            if (onUpdateStrategy) {
                onUpdateStrategy(parsed)
            }
        } catch (err: any) {
            setParseError(err.message || 'Syntax error in ZenScript')
        }
    }, [query])

    const narrative = useMemo(() => generateStrategyNarrative({ ...strategy, ...parsedStrategy }), [strategy, parsedStrategy])

    return (
        <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                <div className="border-b border-slate-100 px-5 py-4 flex justify-between items-center">
                    <div>
                        <div className="flex items-center gap-2">
                            <Sparkles className="h-4 w-4 text-blue-600" />
                            <h3 className="text-sm font-bold text-slate-800">ZenScript Studio</h3>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-slate-500">
                            Write your complete strategy—from symbols to risk—in plain text.
                        </p>
                    </div>
                </div>

                <div className="p-5">
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                        <div className="mb-3 flex items-center justify-between gap-2">
                            <span className="text-xs font-bold uppercase tracking-wide text-slate-500">Editor</span>
                        </div>
                        <div className="relative">
                            <textarea
                                value={query}
                                onChange={(event) => setQuery(event.target.value)}
                                spellCheck={false}
                                className="min-h-[400px] w-full resize-y rounded-lg border border-slate-300 bg-white py-3 px-4 font-mono text-[13px] font-medium leading-relaxed text-emerald-700 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
                            />
                        </div>
                    </div>

                    {parseError ? (
                        <div className="mt-3 rounded-lg bg-red-50 border border-red-100 px-4 py-3 text-xs font-medium leading-5 text-red-700 flex items-start gap-2">
                            <svg className="w-4 h-4 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                            {parseError}
                        </div>
                    ) : (
                        <div className="mt-3 rounded-lg bg-emerald-50 border border-emerald-100 px-4 py-3 text-xs font-medium leading-5 text-emerald-700 flex items-center gap-2">
                            <Check className="w-4 h-4 text-emerald-600" />
                            Compiled successfully
                        </div>
                    )}

                    <div className="mt-4 rounded-lg border border-emerald-100 bg-emerald-50/50 p-4">
                        <div className="text-[11px] font-bold uppercase tracking-wide text-emerald-700 mb-2">
                            Quick Snippets
                        </div>
                        <div className="grid grid-cols-1 gap-3 mt-2">
                            {RULE_TEMPLATES.map(template => (
                                <div key={template.label} className="text-xs bg-white border border-emerald-100 rounded p-3 cursor-pointer hover:border-emerald-300 transition-colors" onClick={() => {
                                    setQuery(template.example);
                                }}>
                                    <span className="block font-semibold text-slate-600 mb-2">{template.label}</span>
                                    <pre className="font-mono text-emerald-800 text-[11px] leading-relaxed overflow-x-auto">{template.example}</pre>
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
                            <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-emerald-500" />
                            <span className="text-slate-700 font-medium">{line}</span>
                        </div>
                    ))}

                    <button
                        type="button"
                        onClick={onSubmitStrategy}
                        disabled={isSubmitting || !!parseError || !parsedStrategy?.symbols?.length || !parsedStrategy?.entry_conditions?.length}
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

function parseFullZenScript(text: string): Partial<StrategyV2> {
    const strategy: Partial<StrategyV2> = {};

    // 1. Strategy Name
    const nameMatch = text.match(/STRATEGY\s+"([^"]+)"/i);
    if (nameMatch) strategy.name = nameMatch[1];

    // 2. Symbols
    const symbolsMatch = text.match(/SYMBOLS:\s*([^\n]+)/i);
    if (symbolsMatch) {
        const symbolsStr = symbolsMatch[1].trim();
        if (symbolsStr !== 'N/A' && symbolsStr !== 'Choose symbols') {
            strategy.symbols = symbolsStr.split(',').map(s => s.trim()).filter(Boolean);
        }
    }

    // 3. Timeframe
    const tfMatch = text.match(/TIMEFRAME:\s*([^\n]+)/i);
    if (tfMatch) strategy.timeframe = tfMatch[1].trim() as any;

    // 4. Date Range
    const dateMatch = text.match(/DATE_RANGE:\s*([\d-]+)\s+to\s+([\d-]+)/i);
    if (dateMatch) {
        strategy.backtest_from = dateMatch[1].trim();
        strategy.backtest_to = dateMatch[2].trim();
    }

    // 5. Entry
    const entryMatch = text.match(/ENTRY\s+(ALL|ANY)\s*\{([^}]+)\}/i);
    if (entryMatch) {
        strategy.entry_logic = entryMatch[1].toUpperCase() as any;
        const conditionsText = entryMatch[2];
        strategy.entry_conditions = parseStrategyQuery(conditionsText);
    }

    // 6. Exit
    const exitMatch = text.match(/EXIT\s+(ALL|ANY)\s*\{([^}]+)\}/i);
    if (exitMatch) {
        strategy.exit_logic = exitMatch[1].toUpperCase() as any;
        const exitText = exitMatch[2];
        strategy.exit_rules = parseExitRules(exitText);
    }

    // 7. Risk
    const riskMatch = text.match(/RISK\s*\{([^}]+)\}/i);
    if (riskMatch) {
        strategy.risk = parseRisk(riskMatch[1]);
    }

    return strategy;
}

function parseExitRules(text: string): ExitRule[] {
    const rules: ExitRule[] = [];
    const lines = text.split('\n').filter(l => l.trim() && !l.trim().startsWith('//'));
    
    lines.forEach((line, index) => {
        const normalized = line.trim().toUpperCase();
        
        // Stoploss
        let match = normalized.match(/STOPLOSS\s+([\d.]+)\s*%/);
        if (match) {
            const trailing = normalized.includes('TRAILING');
            rules.push({
                id: `exit_${Date.now()}_${index}`,
                type: 'stoploss',
                priority: index + 1,
                percent: parseFloat(match[1]),
                trailing,
            });
            return;
        }

        // Target
        match = normalized.match(/TARGET\s+([\d.]+)\s*%/);
        if (match) {
            rules.push({
                id: `exit_${Date.now()}_${index}`,
                type: 'target',
                priority: index + 1,
                percent: parseFloat(match[1]),
            });
            return;
        }

        // Trailing
        match = normalized.match(/TRAILING\s+([\d.]+)\s*%/);
        if (match) {
            const activationMatch = normalized.match(/AFTER\s+([\d.]+)\s*%/);
            rules.push({
                id: `exit_${Date.now()}_${index}`,
                type: 'trailing',
                priority: index + 1,
                percent: parseFloat(match[1]),
                activationPercent: activationMatch ? parseFloat(activationMatch[1]) : undefined
            });
            return;
        }

        // Time
        match = normalized.match(/AT\s+([\d:]+)/);
        if (match) {
            rules.push({
                id: `exit_${Date.now()}_${index}`,
                type: 'time',
                priority: index + 1,
                time: match[1],
            });
            return;
        }
    });

    return rules;
}

function parseRisk(text: string): RiskConfig {
    const risk: RiskConfig = { 
        quantity: 1, 
        max_trades_per_day: 0, 
        max_loss_per_day: 0,
        reentry_after_sl: false,
        max_concurrent_trades: 1
    };
    
    const lines = text.split('\n').filter(l => l.trim() && !l.trim().startsWith('//'));
    lines.forEach(line => {
        const normalized = line.trim().toUpperCase();
        
        let match = normalized.match(/QUANTITY:\s+(\d+)/);
        if (match) risk.quantity = parseInt(match[1], 10);

        match = normalized.match(/MAX_TRADES_DAY:\s+(\d+)/);
        if (match) risk.max_trades_per_day = parseInt(match[1], 10);

        match = normalized.match(/MAX_DAILY_LOSS:\s+(\d+)/);
        if (match) risk.max_loss_per_day = parseInt(match[1], 10);
    });

    return risk;
}

function parseStrategyQuery(query: string): Condition[] {
    const conditions = query
        .split(/\s+AND\s+|\n+/i)
        .map(part => parseConditionQuery(part))
        .filter((condition): condition is Omit<Condition, 'id'> => Boolean(condition));
        
    return conditions.map((c, idx) => ({
        ...c,
        id: `cond_${Date.now()}_${idx}`
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

function generateStrategyNarrative(strategy: Partial<StrategyV2>): string[] {
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

export function generateZenScript(strategy: StrategyV2): string {
    const lines: string[] = []
    const indent = '    '

    lines.push(`STRATEGY "${strategy.name || 'Untitled Strategy'}" {`)
    lines.push(`${indent}SYMBOLS: ${(strategy.symbols || []).join(', ') || 'N/A'}`)
    lines.push(`${indent}TIMEFRAME: ${strategy.timeframe || '15m'}`)

    if (strategy.backtest_from && strategy.backtest_to) {
        lines.push(`${indent}DATE_RANGE: ${strategy.backtest_from} to ${strategy.backtest_to}`)
    }

    lines.push('')
    lines.push(`${indent}ENTRY ${strategy.entry_logic} {`)
    const entryConditions = Array.isArray(strategy.entry_conditions) ? strategy.entry_conditions : []
    if (entryConditions.length === 0) {
        lines.push(`${indent}${indent}// No entry conditions configured`)
    } else {
        entryConditions.forEach((condition) => {
            lines.push(`${indent}${indent}${formatCondition(condition)}`)
        })
    }
    lines.push(`${indent}}`)

    lines.push('')
    lines.push(`${indent}EXIT ${strategy.exit_logic} {`)
    const exitRules = strategy.exit_rules || []
    if (exitRules.length === 0) {
        lines.push(`${indent}${indent}// No exit rules configured`)
    } else {
        exitRules.forEach((rule) => {
            lines.push(`${indent}${indent}${formatExitRule(rule)}`)
        })
    }
    lines.push(`${indent}}`)

    lines.push('')
    lines.push(`${indent}RISK {`)
    lines.push(`${indent}${indent}QUANTITY: ${strategy.risk.quantity}`)
    lines.push(`${indent}${indent}MAX_TRADES_DAY: ${strategy.risk.max_trades_per_day || 'NO_LIMIT'}`)
    lines.push(`${indent}${indent}MAX_DAILY_LOSS: ${strategy.risk.max_loss_per_day || 'NO_CAP'}`)
    lines.push(`${indent}}`)
    lines.push(`}`)

    return lines.join('\n')
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

function formatExitRule(rule: any): string {
    if (!rule?.type) return 'Invalid exit rule'

    switch (rule.type) {
        case 'stoploss':
            return `STOPLOSS ${rule.percent || 0}%${rule.trailing ? ' TRAILING' : ''}`
        case 'target':
            return `TARGET ${rule.percent || 0}%`
        case 'trailing':
            return `TRAILING ${rule.percent || 0}%${rule.activationPercent ? ` AFTER ${rule.activationPercent}%` : ''}`
        case 'time':
            return `AT ${rule.time || '15:15'}`
        case 'indicator_exit':
            return `EXIT WHEN ${formatCondition(rule.condition)}`
        default:
            return `UNKNOWN: ${rule.type}`
    }
}
