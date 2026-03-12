'use client'

import { useState, useEffect, useMemo, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { config, getAuthHeaders } from '@/lib/config'
import { BackButton } from '@/components/BackButton'

const API = config.apiBaseUrl

const T = {
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF', blueMid: '#BFDBFE',
    green: '#059669', greenLight: '#ECFDF5', greenMid: '#A7F3D0',
    red: '#DC2626', redLight: '#FEF2F2', redMid: '#FECACA',
    amber: '#D97706', amberLight: '#FFFBEB',
    text: '#0F172A', textMid: '#475569', textMuted: '#94A3B8',
    border: '#E2E8F0', borderStrong: '#CBD5E1', surface: '#FFFFFF', bg: '#F8FAFC', pill: '#F1F5F9',
}

const STEP_LABELS = ['Asset', 'Timeframe', 'Entry', 'Exit', 'Risk']

const INDICATORS = [
    { id: 'EMA_CROSS', icon: '📈', label: 'EMA Crossover', desc: 'Fast EMA crosses above Slow EMA', params: { fast: 9, slow: 21 } },
    { id: 'RSI_LEVEL', icon: '📊', label: 'RSI Level', desc: 'RSI crosses a threshold level', params: { period: 14, level: 50 } },
    { id: 'SUPERTREND', icon: '⚡', label: 'Supertrend', desc: 'Price crosses above Supertrend', params: { period: 7, multiplier: 3 } },
    { id: 'PRICE_ACTION', icon: '🕯️', label: 'Price Action', desc: 'Engulfing / breakout candle', params: {} },
]

type EntryCondition = { indicator: string; params: Record<string, number>; logic: 'AND' | 'OR' }
type Strategy = {
    name: string; asset_type: 'EQUITY' | 'FNO'; symbol: string;
    index: string; option_type: string; strike_type: string; timeframe: string
    entry_conditions: EntryCondition[]
    exit_conditions: { target_pct: number; stoploss_pct: number; trailing_sl_pct: number; time_exit: string }
    risk: { max_trades_per_day: number; max_loss_per_day: number; quantity_lots: number; lot_size: number; reentry_after_sl: boolean }
    backtest_from: string; backtest_to: string
}

const DEFAULT: Strategy = {
    name: '', asset_type: 'EQUITY', symbol: 'RELIANCE',
    index: 'NIFTY', option_type: 'CE', strike_type: 'ATM', timeframe: '1D',
    entry_conditions: [],
    exit_conditions: { target_pct: 5, stoploss_pct: 3, trailing_sl_pct: 0, time_exit: '15:15' },
    risk: { max_trades_per_day: 3, max_loss_per_day: 5000, quantity_lots: 10, lot_size: 1, reentry_after_sl: false },
    backtest_from: '',
    backtest_to: '',
}

function Card({ children, style = {} }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return <div style={{ background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`, boxShadow: '0 1px 3px rgba(0,0,0,0.04)', padding: 20, ...style }}>{children}</div>
}

function ToggleGroup({ options, value, onSelect }: { options: string[]; value: string; onSelect: (v: string) => void }) {
    return (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {options.map(opt => (
                <button key={opt} onClick={() => onSelect(opt)} style={{
                    padding: '8px 16px', borderRadius: 8, border: `1px solid ${value === opt ? T.blue : T.border}`,
                    background: value === opt ? T.blueLight : '#fff',
                    color: value === opt ? T.blue : T.textMid,
                    fontSize: 13, fontWeight: value === opt ? 700 : 500, cursor: 'pointer', transition: 'all 0.15s',
                }}>{opt}</button>
            ))}
        </div>
    )
}

// ── Steps ─────────────────────────────────────────────────────────────────────
function Step1({ d, s, selectedStocks, fromScreener }: { d: Strategy; s: (x: Partial<Strategy>) => void, selectedStocks: string[], fromScreener: boolean }) {
    const [symbols, setSymbols] = useState<string[]>([])
    const [search, setSearch] = useState('')

    useEffect(() => {
        fetch(`${API}/api/strategy/symbols`)
            .then(r => r.json())
            .then(setSymbols)
            .catch(() => setSymbols(['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']))
    }, [])

    const filtered = useMemo(() => {
        if (!search) return symbols.slice(0, 50)
        return symbols.filter(s => s.toLowerCase().includes(search.toLowerCase())).slice(0, 50)
    }, [symbols, search])

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Asset Type</p>
                <ToggleGroup options={['EQUITY', 'FNO']} value={d.asset_type} onSelect={v => s({ asset_type: v as 'EQUITY' | 'FNO' })} />
            </div>

            {d.asset_type === 'EQUITY' ? (
                <div>
                    {fromScreener ? (
                        // Screener mode: show selected stocks as chips
                        <div>
                            <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                                Selected Stocks from Screener
                            </p>
                            <div style={{
                                padding: '12px', background: T.greenLight,
                                borderRadius: 8, border: `1px solid ${T.green}`,
                                marginBottom: 12
                            }}>
                                <div style={{ fontSize: 12, fontWeight: 600, color: T.green, marginBottom: 8 }}>
                                    📊 {selectedStocks.length} stocks selected
                                </div>
                                <div style={{
                                    display: 'flex', flexWrap: 'wrap', gap: 6,
                                    maxHeight: 120, overflowY: 'auto'
                                }}>
                                    {selectedStocks.slice(0, 20).map(sym => (
                                        <span key={sym} style={{
                                            padding: '4px 8px', background: T.surface,
                                            borderRadius: 4, fontSize: 11, fontWeight: 600,
                                            fontFamily: "'DM Mono', monospace", color: T.blue
                                        }}>{sym}</span>
                                    ))}
                                    {selectedStocks.length > 20 && (
                                        <span style={{ fontSize: 11, color: T.textMuted }}>
                                            +{selectedStocks.length - 20} more
                                        </span>
                                    )}
                                </div>
                            </div>
                            <p style={{ fontSize: 11, color: T.textMuted }}>
                                These stocks will be used for backtesting. The strategy will be tested on each stock individually.
                            </p>
                        </div>
                    ) : (
                        // Normal mode: single stock selection
                        <div>
                            <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                                Stock Symbol <span style={{ color: T.blue, textTransform: 'none', letterSpacing: 0 }}>({symbols.length} available)</span>
                            </p>
                            <input
                                placeholder="Search stocks (e.g. RELIANCE, TCS)..."
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                                style={{
                                    width: '100%', padding: '9px 12px', border: `1px solid ${T.border}`, borderRadius: 8,
                                    fontSize: 13, fontFamily: "'DM Sans', sans-serif", marginBottom: 10, outline: 'none',
                                }}
                            />
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, maxHeight: 180, overflowY: 'auto', padding: 2 }}>
                                {filtered.map(sym => (
                                    <button key={sym} onClick={() => { s({ symbol: sym }); setSearch('') }} style={{
                                        padding: '6px 12px', borderRadius: 6, border: `1px solid ${d.symbol === sym ? T.blue : T.border}`,
                                        background: d.symbol === sym ? T.blue : '#fff',
                                        color: d.symbol === sym ? '#fff' : T.textMid,
                                        fontSize: 12, fontWeight: d.symbol === sym ? 700 : 500, cursor: 'pointer',
                                        fontFamily: "'DM Mono', monospace", transition: 'all 0.12s',
                                    }}>{sym}</button>
                                ))}
                                {filtered.length === 0 && <span style={{ fontSize: 12, color: T.textMuted }}>No matches</span>}
                            </div>
                            {d.symbol && (
                                <div style={{ marginTop: 10, padding: '8px 12px', background: T.blueLight, borderRadius: 8, border: `1px solid ${T.blueMid}` }}>
                                    <span style={{ fontSize: 12, color: T.textMid }}>Selected: </span>
                                    <span style={{ fontSize: 14, fontWeight: 800, color: T.blue, fontFamily: "'DM Mono', monospace" }}>{d.symbol}</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            ) : (
                <>
                    <div>
                        <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Select Index</p>
                        <ToggleGroup options={['NIFTY', 'BANKNIFTY', 'FINNIFTY']} value={d.index} onSelect={v => s({ index: v })} />
                    </div>
                    <div>
                        <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Option Type</p>
                        <ToggleGroup options={['CE', 'PE', 'BOTH']} value={d.option_type} onSelect={v => s({ option_type: v })} />
                    </div>
                    <div>
                        <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Strike</p>
                        <ToggleGroup options={['ATM', 'OTM1', 'OTM2', 'OTM3', 'ITM1', 'ITM2', 'ITM3']} value={d.strike_type} onSelect={v => s({ strike_type: v })} />
                        <p style={{ fontSize: 12, color: T.textMuted, marginTop: 6 }}>ATM = At the Money · OTM = Out · ITM = In</p>
                    </div>
                </>
            )}
        </div>
    )
}

function Step2({ d, s }: { d: Strategy; s: (x: Partial<Strategy>) => void }) {
    const timeframes = d.asset_type === 'EQUITY'
        ? [['1min', '1 Minute', 'Fastest - real-time scalping'], ['5min', '5 Minute', 'Best for intraday scalping'], ['15min', '15 Minute', 'Best for intraday trends'], ['1D', 'Daily', 'Best for swing/positional strategies']]
        : [['1min', '1 Minute', 'Fastest scalping'], ['5min', '5 Minute', 'Best for intraday scalping'], ['15min', '15 Minute', 'Best for trend strategies']]

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Candle Timeframe</p>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    {timeframes.map(([v, l, desc]) => (
                        <button key={v} onClick={() => s({ timeframe: v })} style={{
                            flex: 1, minWidth: 160, padding: 16, borderRadius: 10, border: `2px solid ${d.timeframe === v ? T.blue : T.border}`,
                            background: d.timeframe === v ? T.blueLight : '#fff', cursor: 'pointer', textAlign: 'left',
                        }}>
                            <div style={{ fontSize: 16, fontWeight: 800, color: d.timeframe === v ? T.blue : T.navy, marginBottom: 4 }}>{l}</div>
                            <div style={{ fontSize: 12, color: T.textMuted }}>{desc}</div>
                        </button>
                    ))}
                </div>
            </div>
            <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Backtest Period</p>
                <div style={{ display: 'flex', gap: 12 }}>
                    <div style={{ flex: 1 }}>
                        <p style={{ fontSize: 11, color: T.textMuted, marginBottom: 4 }}>From</p>
                        <input type="date" value={d.backtest_from}
                            onChange={e => s({ backtest_from: e.target.value })}
                            style={{ width: '100%', padding: '9px 12px', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, fontFamily: "'DM Sans', sans-serif" }} />
                    </div>
                    <div style={{ flex: 1 }}>
                        <p style={{ fontSize: 11, color: T.textMuted, marginBottom: 4 }}>To</p>
                        <input type="date" value={d.backtest_to}
                            onChange={e => s({ backtest_to: e.target.value })}
                            style={{ width: '100%', padding: '9px 12px', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, fontFamily: "'DM Sans', sans-serif" }} />
                    </div>
                </div>
            </div>
        </div>
    )
}

function Step3({ d, s }: { d: Strategy; s: (x: Partial<Strategy>) => void }) {
    const add = (id: string) => {
        if (d.entry_conditions.find(c => c.indicator === id)) return
        const meta = INDICATORS.find(i => i.id === id)!
        s({ entry_conditions: [...d.entry_conditions, { indicator: id, params: { ...meta.params } as Record<string, number>, logic: 'AND' }] })
    }
    const remove = (id: string) => s({ entry_conditions: d.entry_conditions.filter(c => c.indicator !== id) })
    const updateParam = (idx: number, k: string, v: number) => {
        const conds = [...d.entry_conditions]
        conds[idx] = { ...conds[idx], params: { ...conds[idx].params, [k]: v } }
        s({ entry_conditions: conds })
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Add Indicators <span style={{ color: T.blue, textTransform: 'none', letterSpacing: 0 }}>(click to add)</span></p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    {INDICATORS.map(ind => {
                        const active = d.entry_conditions.some(c => c.indicator === ind.id)
                        return (
                            <button key={ind.id} onClick={() => add(ind.id)} style={{
                                textAlign: 'left', padding: 14, borderRadius: 10, cursor: 'pointer',
                                border: `2px solid ${active ? T.blue : T.border}`,
                                background: active ? T.blueLight : '#fff', transition: 'all 0.15s',
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                    <span style={{ fontSize: 18 }}>{ind.icon}</span>
                                    <span style={{ fontSize: 13, fontWeight: 700, color: active ? T.blue : T.navy }}>{ind.label}</span>
                                    {active && <span style={{ marginLeft: 'auto', background: T.greenLight, color: T.green, borderRadius: 4, padding: '1px 6px', fontSize: 10, fontWeight: 700 }}>✓ Added</span>}
                                </div>
                                <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>{ind.desc}</p>
                            </button>
                        )
                    })}
                </div>
            </div>

            {d.entry_conditions.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>Configure Parameters</p>
                    {d.entry_conditions.map((cond, idx) => {
                        const meta = INDICATORS.find(i => i.id === cond.indicator)!
                        return (
                            <div key={cond.indicator} style={{ border: `1px solid ${T.border}`, borderRadius: 10, padding: 14 }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                                    <span style={{ fontSize: 14, fontWeight: 700, color: T.navy }}>{meta.icon} {meta.label}</span>
                                    <button onClick={() => remove(cond.indicator)} style={{ background: 'none', border: 'none', color: T.red, fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>Remove</button>
                                </div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
                                    {Object.entries(cond.params).map(([k, v]) => (
                                        <div key={k}>
                                            <p style={{ fontSize: 11, color: T.textMuted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>{k}</p>
                                            <input type="number" value={v} onChange={e => updateParam(idx, k, Number(e.target.value))}
                                                style={{ width: 80, padding: '7px 10px', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, fontFamily: "'DM Mono', monospace" }} />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )
                    })}
                    {d.entry_conditions.length > 1 && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{ fontSize: 12, color: T.textMid }}>Combine with:</span>
                            {(['AND', 'OR'] as const).map(l => (
                                <button key={l} onClick={() => s({ entry_conditions: d.entry_conditions.map(c => ({ ...c, logic: l })) })} style={{
                                    padding: '4px 14px', border: `1px solid ${d.entry_conditions[0]?.logic === l ? T.blue : T.border}`,
                                    borderRadius: 6, background: d.entry_conditions[0]?.logic === l ? T.blue : '#fff',
                                    color: d.entry_conditions[0]?.logic === l ? '#fff' : T.textMid, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                                }}>{l}</button>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

function Step4({ d, s }: { d: Strategy; s: (x: Partial<Strategy>) => void }) {
    const ex = d.exit_conditions
    const upd = (k: keyof typeof ex, v: any) => s({ exit_conditions: { ...ex, [k]: v } })
    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {[
                { k: 'target_pct', label: '🎯 Target Profit (%)', hint: 'Exit when price gains this %' },
                { k: 'stoploss_pct', label: '🛑 Stop Loss (%)', hint: 'Exit when price loses this %' },
                { k: 'trailing_sl_pct', label: '📉 Trailing Stop Loss (%)', hint: 'Trail from highest point' },
            ].map(({ k, label, hint }) => (
                <div key={k}>
                    <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>{label}</p>
                    <input type="number" value={(ex as any)[k] || ''} placeholder="e.g. 5"
                        onChange={e => upd(k as any, Number(e.target.value))}
                        style={{ width: '100%', padding: '9px 12px', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, fontFamily: "'DM Sans', sans-serif" }} />
                    <p style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>{hint}</p>
                </div>
            ))}
            {d.asset_type === 'FNO' && (
                <div>
                    <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>⏰ Time Exit (IST)</p>
                    <input type="time" value={ex.time_exit} onChange={e => upd('time_exit', e.target.value)}
                        style={{ width: '100%', padding: '9px 12px', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, fontFamily: "'DM Sans', sans-serif" }} />
                    <p style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>Force-exit at this time regardless</p>
                </div>
            )}
        </div>
    )
}

function Step5({ d, s }: { d: Strategy; s: (x: Partial<Strategy>) => void }) {
    const r = d.risk
    const upd = (k: keyof typeof r, v: any) => s({ risk: { ...r, [k]: v } })
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                {[
                    { k: 'max_trades_per_day', label: 'Max Trades Per Day' },
                    { k: 'max_loss_per_day', label: 'Max Loss Per Day (Rs.)' },
                    { k: 'quantity_lots', label: d.asset_type === 'EQUITY' ? 'Number of Shares' : 'Number of Lots' },
                    { k: 'lot_size', label: d.asset_type === 'EQUITY' ? 'Lot Size (keep 1 for stocks)' : 'Lot Size (e.g. 50 for NIFTY)' },
                ].map(({ k, label }) => (
                    <div key={k}>
                        <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>{label}</p>
                        <input type="number" value={(r as any)[k]} onChange={e => upd(k as any, Number(e.target.value))}
                            style={{ width: '100%', padding: '9px 12px', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, fontFamily: "'DM Sans', sans-serif" }} />
                    </div>
                ))}
                <div>
                    <p style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Re-entry After Stop Loss?</p>
                    <div style={{ display: 'flex', gap: 8 }}>
                        {[['Yes', true], ['No', false]].map(([l, v]) => (
                            <button key={String(l)} onClick={() => upd('reentry_after_sl', v)} style={{
                                flex: 1, padding: '8px', border: `2px solid ${r.reentry_after_sl === v ? T.blue : T.border}`,
                                borderRadius: 8, background: r.reentry_after_sl === v ? T.blueLight : '#fff',
                                color: r.reentry_after_sl === v ? T.blue : T.textMid, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                            }}>{l as string}</button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Summary card */}
            <div style={{ background: T.blueLight, borderRadius: 10, border: `1px solid ${T.blueMid}`, padding: 16 }}>
                <p style={{ fontSize: 12, fontWeight: 700, color: T.navy, marginBottom: 10 }}>Strategy Summary</p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 12, color: T.textMid }}>
                    <span>Type: <b style={{ color: T.navy }}>{d.asset_type}</b></span>
                    {d.asset_type === 'EQUITY' ? (
                        <span>Symbol: <b style={{ color: T.blue }}>{d.symbol}</b></span>
                    ) : (
                        <>
                            <span>Index: <b style={{ color: T.navy }}>{d.index}</b></span>
                            <span>Option: <b style={{ color: T.navy }}>{d.option_type}</b></span>
                            <span>Strike: <b style={{ color: T.navy }}>{d.strike_type}</b></span>
                        </>
                    )}
                    <span>Timeframe: <b style={{ color: T.navy }}>{d.timeframe}</b></span>
                    <span>Indicators: <b style={{ color: T.navy }}>{d.entry_conditions.map(c => c.indicator).join(', ') || 'None'}</b></span>
                    <span>Target: <b style={{ color: T.green }}>{d.exit_conditions.target_pct || '—'}%</b></span>
                    <span>Period: <b style={{ color: T.navy }}>{d.backtest_from} → {d.backtest_to}</b></span>
                </div>
            </div>
        </div>
    )
}

// ── Main ───────────────────────────────────────────────────────────────────────
function NewStrategyContent() {
    const [step, setStep] = useState(0)
    const [data, setData] = useState<Strategy>(DEFAULT)
    const [loading, setLoading] = useState(false)
    const router = useRouter()
    const searchParams = useSearchParams()

    // Multi-stock support from screener
    const [selectedStocks, setSelectedStocks] = useState<string[]>([])
    const [fromScreener, setFromScreener] = useState(false)
    const [showDeployModal, setShowDeployModal] = useState(false)
    const [selectedBroker, setSelectedBroker] = useState('dhan')
    const [isPaper, setIsPaper] = useState(false)

    const set = (partial: Partial<Strategy>) => setData(p => ({ ...p, ...partial }))

    useEffect(() => {
        setData(p => ({
            ...p,
            backtest_from: new Date(Date.now() - 365 * 86400000).toISOString().split('T')[0],
            backtest_to: new Date().toISOString().split('T')[0]
        }))
    }, [])

    // Handle URL params from screener and edit
    useEffect(() => {
        const stocksParam = searchParams.get('stocks')
        const source = searchParams.get('source')
        const editId = searchParams.get('edit')

        if (editId) {
            // Edit mode
            setLoading(true)
            fetch(`${API}/api/strategy/${editId}`, { headers: getAuthHeaders() })
                .then(res => {
                    if (!res.ok) throw new Error('Failed to fetch strategy')
                    return res.json()
                })
                .then(strategy => {
                    setData({
                        name: strategy.name || '',
                        asset_type: strategy.asset_type || 'EQUITY',
                        symbol: (strategy.symbols && strategy.symbols.length > 0) ? strategy.symbols[0] : (strategy.symbol || ''),
                        index: strategy.index || 'NIFTY',
                        option_type: strategy.option_type || 'CE',
                        strike_type: strategy.strike_type || 'ATM',
                        timeframe: strategy.timeframe || '1D',
                        entry_conditions: strategy.entry_conditions || [],
                        exit_conditions: strategy.exit_conditions || { target_pct: 5, stoploss_pct: 3, trailing_sl_pct: 0, time_exit: '15:15' },
                        risk: strategy.risk || { max_trades_per_day: 3, max_loss_per_day: 5000, quantity_lots: 10, lot_size: 1, reentry_after_sl: false },
                        backtest_from: strategy.backtest_from || new Date(Date.now() - 365 * 86400000).toISOString().split('T')[0],
                        backtest_to: strategy.backtest_to || new Date().toISOString().split('T')[0],
                    })
                })
                .catch(err => {
                    console.error("Error loading strategy to edit:", err)
                    alert("Could not load strategy for editing.")
                })
                .finally(() => setLoading(false))
        } else if (stocksParam && source === 'screener') {
            const stocks = stocksParam.split(',').filter(Boolean)
            if (stocks.length > 0) {
                setSelectedStocks(stocks)
                setFromScreener(true)
                // Set first stock as default symbol
                setData(p => ({ ...p, symbol: stocks[0] }))
            }
        }
    }, [searchParams])

    const submit = async () => {
        if (!data.name.trim()) { alert('Please enter a strategy name'); return }
        if (data.asset_type === 'EQUITY' && selectedStocks.length === 0 && !data.symbol) {
            alert('Please select a stock symbol');
            return
        }
        if (data.entry_conditions.length === 0) {
            alert('Please add at least one entry indicator');
            return
        }

        setLoading(true)
        const editId = searchParams.get('edit')
        
        try {
            const payload: any = {
                name: data.name,
                asset_type: data.asset_type,
                timeframe: data.timeframe,
                entry_conditions: data.entry_conditions,
                exit_conditions: data.exit_conditions,
                risk: data.risk,
                backtest_from: data.backtest_from,
                backtest_to: data.backtest_to,
            }
            if (data.asset_type === 'EQUITY') {
                payload.symbols = fromScreener && selectedStocks.length > 0 ? selectedStocks : [data.symbol]
            } else {
                payload.index = data.index
                payload.option_type = data.option_type
                payload.strike_type = data.strike_type
            }

            const url = editId ? `${API}/api/strategy/${editId}` : `${API}/api/strategy`
            const method = editId ? 'PUT' : 'POST'

            const res = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
                body: JSON.stringify(payload)
            })
            if (!res.ok) {
                const err = await res.json()
                alert(`Error creating strategy: ${JSON.stringify(err.detail || err)}`)
                setLoading(false)
                return
            }
            const { strategy_id } = await res.json()

            const bt = await fetch(`${API}/api/backtest/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
                body: JSON.stringify({ strategy_id })
            })
            if (!bt.ok) {
                const err = await bt.json()
                alert(`Error running backtest: ${JSON.stringify(err.detail || err)}`)
                setLoading(false)
                return
            }
            const { backtest_id } = await bt.json()
            router.push(`/backtest/${backtest_id}`)
        } catch (err: any) {
            console.error(err)
            alert('Error — make sure the backend is running and data is updated.')
        }
        finally {
            setLoading(false)
        }
    }

    const deployLive = async () => {
        if (!data.name.trim()) { alert('Please enter a strategy name'); return }
        setLoading(true)
        const editId = searchParams.get('edit')
        
        try {
            // 1. Save strategy first
            const payload: any = {
                name: data.name,
                asset_type: data.asset_type,
                timeframe: data.timeframe,
                entry_conditions: data.entry_conditions,
                exit_conditions: data.exit_conditions,
                risk: data.risk,
            }
            if (data.asset_type === 'EQUITY') {
                payload.symbols = fromScreener && selectedStocks.length > 0 ? selectedStocks : [data.symbol]
            } else {
                payload.index = data.index
                payload.option_type = data.option_type
                payload.strike_type = data.strike_type
            }

            const url = editId ? `${API}/api/strategy/${editId}` : `${API}/api/strategy`
            const method = editId ? 'PUT' : 'POST'

            const sres = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
                body: JSON.stringify(payload)
            })
            if (!sres.ok) {
                const err = await sres.json()
                alert(`Error saving strategy: ${JSON.stringify(err.detail || err)}`)
                setLoading(false)
                return
            }
            const { strategy_id } = await sres.json()

            // 2. Deploy
            const dres = await fetch(`${API}/api/live/deploy`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
                body: JSON.stringify({ strategy_id, broker: selectedBroker, paper: isPaper })
            })
            if (!dres.ok) {
                const err = await dres.json()
                alert(`Error deploying strategy: ${JSON.stringify(err.detail || err)}`)
                setLoading(false)
                return
            }

            router.push('/live')
        } catch (err) {
            alert('Error deploying strategy. Check backend logs.')
        } finally {
            setLoading(false)
        }
    }

    const steps = [
        <Step1 key={0} d={data} s={set} selectedStocks={selectedStocks} fromScreener={fromScreener} />,
        <Step2 key={1} d={data} s={set} />,
        <Step3 key={2} d={data} s={set} />,
        <Step4 key={3} d={data} s={set} />,
        <Step5 key={4} d={data} s={set} />,
    ]

    return (
        <div style={{ maxWidth: 680, margin: '0 auto', padding: 24, fontFamily: "'DM Sans', sans-serif" }}>
            {/* Header with Back Button */}
            <div style={{ marginBottom: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                    <BackButton defaultBack="/dashboard" />
                    <h1 style={{ fontSize: 22, fontWeight: 800, color: T.navy, margin: 0, letterSpacing: '-0.5px' }}>
                        Build Your Strategy
                    </h1>
                </div>
                <input placeholder="Strategy name (e.g. RELIANCE EMA Breakout)" value={data.name} onChange={e => set({ name: e.target.value })}
                    style={{ width: '100%', padding: '11px 14px', border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 15, fontWeight: 600, fontFamily: "'DM Sans', sans-serif", color: T.navy, outline: 'none' }} />
            </div>

            {/* Step progress */}
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 24 }}>
                {STEP_LABELS.map((label, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                            <div onClick={() => i < step && setStep(i)} style={{
                                width: 32, height: 32, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: 13, fontWeight: 700, transition: 'all 0.15s', cursor: i < step ? 'pointer' : 'default',
                                border: `2px solid ${i === step ? T.blue : i < step ? T.green : T.border}`,
                                background: i === step ? T.blue : i < step ? T.green : '#fff',
                                color: i <= step ? '#fff' : T.textMuted,
                            }}>{i < step ? '✓' : i + 1}</div>
                            <span style={{ fontSize: 10, marginTop: 4, color: i === step ? T.blue : T.textMuted, fontWeight: i === step ? 700 : 400 }}>{label}</span>
                        </div>
                        {i < 4 && <div style={{ width: 40, height: 2, background: i < step ? T.green : T.border, margin: '0 2px 14px' }} />}
                    </div>
                ))}
            </div>

            {/* Step content */}
            <Card style={{ marginBottom: 20, minHeight: 300 }}>
                <h2 style={{ fontSize: 15, fontWeight: 700, color: T.navy, margin: '0 0 18px' }}>Step {step + 1}: {STEP_LABELS[step]}</h2>
                {steps[step]}
            </Card>

            {/* Navigation */}
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <button onClick={() => setStep(s => s - 1)} disabled={step === 0} style={{
                    padding: '10px 20px', border: `1px solid ${T.border}`, borderRadius: 8,
                    background: '#fff', color: T.textMid, fontSize: 13, fontWeight: 600, cursor: step === 0 ? 'not-allowed' : 'pointer', opacity: step === 0 ? 0.4 : 1,
                }}>← Back</button>
                {step < 4 ? (
                    <button onClick={() => setStep(s => s + 1)} style={{ padding: '10px 24px', background: T.blue, color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>Next →</button>
                ) : (
                    <div style={{ display: 'flex', gap: 10 }}>
                        <button onClick={() => setShowDeployModal(true)} disabled={loading} style={{ padding: '10px 20px', background: T.green, color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer', opacity: loading ? 0.7 : 1 }}>
                            🚀 Deploy Live
                        </button>
                        <button onClick={submit} disabled={loading} style={{ padding: '10px 20px', background: T.blue, color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer', opacity: loading ? 0.7 : 1 }}>
                            {loading ? '⏳ Waiting...' : '📊 Run Backtest'}
                        </button>
                    </div>
                )}
            </div>

            {/* Deploy Modal */}
            {showDeployModal && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
                    <div style={{ background: '#fff', borderRadius: 16, padding: 32, maxWidth: 420, width: '90%', boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
                        <h2 style={{ fontSize: 18, fontWeight: 800, color: T.navy, margin: '0 0 6px' }}>Ready to Go Live?</h2>
                        <p style={{ fontSize: 13, color: T.textMuted, margin: '0 0 24px' }}>Choose your broker and execution mode.</p>

                        <div style={{ marginBottom: 16 }}>
                            <label style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: 8 }}>Broker</label>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                                {['dhan', 'zerodha', 'shoonya', 'flattrade'].map(b => (
                                    <button key={b} onClick={() => setSelectedBroker(b)} style={{
                                        padding: '10px', border: `2px solid ${selectedBroker === b ? T.blue : T.border}`,
                                        borderRadius: 8, background: selectedBroker === b ? T.blueLight : '#fff',
                                        color: selectedBroker === b ? T.blue : T.textMid, fontSize: 13, fontWeight: 600, cursor: 'pointer', textTransform: 'capitalize'
                                    }}>{b}</button>
                                ))}
                            </div>
                        </div>

                        <div style={{ marginBottom: 24 }}>
                            <label style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: 8 }}>Mode</label>
                            <div style={{ display: 'flex', gap: 8 }}>
                                {[['Live', false], ['Paper', true]].map(([l, v]) => (
                                    <button key={String(l)} onClick={() => setIsPaper(v as boolean)} style={{
                                        flex: 1, padding: '10px', border: `2px solid ${isPaper === v ? T.blue : T.border}`,
                                        borderRadius: 8, background: isPaper === v ? T.blueLight : '#fff',
                                        color: isPaper === v ? T.blue : T.textMid, fontSize: 13, fontWeight: 600, cursor: 'pointer'
                                    }}>{l as string}</button>
                                ))}
                            </div>
                        </div>

                        <div style={{ display: 'flex', gap: 10 }}>
                            <button onClick={() => setShowDeployModal(false)} style={{ flex: 1, padding: 12, border: `1px solid ${T.border}`, borderRadius: 8, background: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', color: T.textMid }}>Cancel</button>
                            <button onClick={deployLive} disabled={loading} style={{ flex: 1, padding: 12, border: 'none', borderRadius: 8, background: T.green, fontSize: 13, fontWeight: 700, cursor: 'pointer', color: '#fff' }}>
                                {loading ? 'Deploying...' : '🚀 Start Trading'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

export default function NewStrategyPage() {
    return (
        <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>Loading...</div>}>
            <NewStrategyContent />
        </Suspense>
    )
}
