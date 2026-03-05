'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { config } from '@/lib/config'

const T = {
    bg: '#F8FAFC', surface: '#FFFFFF', surfaceHover: '#F1F5F9',
    border: '#E2E8F0', borderStrong: '#CBD5E1',
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF', blueMid: '#BFDBFE',
    green: '#059669', greenLight: '#ECFDF5',
    text: '#0F172A', textMid: '#475569', textMuted: '#94A3B8',
}

interface ScreenerDesc {
    id: string
    name: string
    params: Record<string, any>
}

interface ScreenerResult {
    symbol: string
    [key: string]: any
}

export function StocksView() {
    const [stocks, setStocks] = useState<string[]>([])
    const [search, setSearch] = useState('')
    const [loading, setLoading] = useState(true)

    // Screener states
    const [screeners, setScreeners] = useState<ScreenerDesc[]>([])
    const [selectedScreeners, setSelectedScreeners] = useState<string[]>([])
    const [screenerResults, setScreenerResults] = useState<ScreenerResult[] | null>(null)
    const [runningScreener, setRunningScreener] = useState(false)
    
    // Parameter customization
    const [customParams, setCustomParams] = useState<Record<string, Record<string, any>>>({})
    const [showAdvanced, setShowAdvanced] = useState(false)

    useEffect(() => {
        const fetchStocksAndScreeners = async () => {
            try {
                const [stocksRes, screenersRes] = await Promise.all([
                    fetch(`${config.apiBaseUrl}/api/stocks`),
                    fetch(`${config.apiBaseUrl}/api/screeners/list`)
                ])
                if (stocksRes.ok) {
                    const data = await stocksRes.json()
                    setStocks(data.stocks || [])
                }
                if (screenersRes.ok) {
                    const data = await screenersRes.json()
                    setScreeners(data.screeners || [])
                    // Initialize custom params with defaults
                    const defaults: Record<string, Record<string, any>> = {}
                    data.screeners.forEach((sc: ScreenerDesc) => {
                        defaults[sc.id] = { ...sc.params }
                    })
                    setCustomParams(defaults)
                }
            } catch (error) {
                console.error('Failed to fetch data:', error)
            } finally {
                setLoading(false)
            }
        }
        fetchStocksAndScreeners()
    }, [])

    const displayItems = screenerResults
        ? screenerResults.filter(r => r.symbol.toLowerCase().includes(search.toLowerCase()))
        : stocks.filter(s => s.toLowerCase().includes(search.toLowerCase()))

    const handleRunScreener = async () => {
        if (selectedScreeners.length === 0) {
            setScreenerResults(null)
            return
        }
        setRunningScreener(true)
        try {
            // Build params object: screener_id -> custom params
            const paramsObj: Record<string, any> = {}
            selectedScreeners.forEach(id => {
                paramsObj[id] = customParams[id] || {}
            })
            
            const res = await fetch(`${config.apiBaseUrl}/api/screeners/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    screener_ids: selectedScreeners,
                    params: paramsObj
                })
            })
            if (res.ok) {
                const data = await res.json()
                setScreenerResults(data.results || [])
            }
        } catch (error) {
            console.error('Failed to run screener:', error)
        } finally {
            setRunningScreener(false)
        }
    }

    const toggleScreener = (id: string) => {
        setSelectedScreeners(prev => 
            prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
        )
    }

    const updateParam = (screenerId: string, paramKey: string, value: any) => {
        setCustomParams(prev => ({
            ...prev,
            [screenerId]: {
                ...prev[screenerId],
                [paramKey]: value
            }
        }))
    }

    const handleBuildStrategy = () => {
        if (!screenerResults || screenerResults.length === 0) return
        const symbols = screenerResults.map(r => r.symbol).join(',')
        window.location.href = `/strategy/new?stocks=${symbols}&source=screener`
    }

    const formatMetric = (key: string, val: any) => {
        if (typeof val === 'number') {
            if (key.includes('pct') || key.includes('ratio')) return `${val}%`
            return val.toLocaleString()
        }
        return String(val)
    }

    return (
        <div style={{ padding: '0 0 24px' }}>
            <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                marginBottom: 20, background: T.surface, padding: '16px 20px',
                borderRadius: 12, border: `1px solid ${T.border}`
            }}>
                <div>
                    <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: T.navy }}>Nifty 500 Stocks</h2>
                    <p style={{ margin: '2px 0 0', fontSize: 12, color: T.textMuted }}>
                        Browse and analyze individual stocks
                    </p>
                </div>

                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                    {/* Screener Multi-Select Dropdown */}
                    <div style={{ position: 'relative' }}>
                        <select
                            value=""
                            onChange={(e) => {
                                if (e.target.value) toggleScreener(e.target.value)
                            }}
                            style={{
                                padding: '10px 12px', borderRadius: 8, border: `1px solid ${T.borderStrong}`,
                                fontSize: 13, outline: 'none', background: T.surface, color: T.navy, fontWeight: 500,
                                minWidth: 200
                            }}
                        >
                            <option value="">+ Add Screener...</option>
                            {screeners.filter(sc => !selectedScreeners.includes(sc.id)).map(sc => (
                                <option key={sc.id} value={sc.id}>{sc.name}</option>
                            ))}
                        </select>
                    </div>

                    <button
                        onClick={handleRunScreener}
                        disabled={selectedScreeners.length === 0 || runningScreener}
                        style={{
                            padding: '10px 16px', borderRadius: 8, border: 'none',
                            background: selectedScreeners.length > 0 ? T.blue : T.border,
                            color: selectedScreeners.length > 0 ? '#fff' : T.textMuted,
                            fontSize: 13, fontWeight: 600, cursor: selectedScreeners.length > 0 && !runningScreener ? 'pointer' : 'not-allowed',
                            transition: 'all 0.2s'
                        }}
                    >
                        {runningScreener ? 'Scanning...' : `Run Screener${selectedScreeners.length > 1 ? ` (${selectedScreeners.length})` : ''}`}
                    </button>

                    <button
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        disabled={selectedScreeners.length === 0}
                        style={{
                            padding: '10px 16px', borderRadius: 8, border: `1px solid ${T.borderStrong}`,
                            background: showAdvanced ? T.blueLight : T.surface,
                            color: selectedScreeners.length > 0 ? T.blue : T.textMuted,
                            fontSize: 13, fontWeight: 600, cursor: selectedScreeners.length > 0 ? 'pointer' : 'not-allowed',
                            transition: 'all 0.2s'
                        }}
                    >
                        {showAdvanced ? 'Hide' : 'Advanced'} ⚙
                    </button>

                    <div style={{ position: 'relative', marginLeft: 8 }}>
                        <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 14 }}>🔍</span>
                        <input
                            type="text"
                            placeholder="Search symbols..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            style={{
                                padding: '10px 12px 10px 36px',
                                borderRadius: 8,
                                border: `1px solid ${T.borderStrong}`,
                                fontSize: 14,
                                width: 200,
                                outline: 'none',
                                transition: 'border-color 0.2s',
                            }}
                            onFocus={(e) => e.target.style.borderColor = T.blue}
                            onBlur={(e) => e.target.style.borderColor = T.borderStrong}
                        />
                    </div>
                </div>
            </div>

            {/* Selected Screeners Chips */}
            {selectedScreeners.length > 0 && (
                <div style={{
                    display: 'flex', flexWrap: 'wrap', gap: 8,
                    marginBottom: 16, padding: '12px 16px',
                    background: T.blueLight, borderRadius: 8,
                    border: `1px solid ${T.blueMid}`
                }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: T.navy, alignSelf: 'center' }}>Active:</span>
                    {selectedScreeners.map(id => {
                        const sc = screeners.find(s => s.id === id)
                        return (
                            <span key={id} style={{
                                display: 'flex', alignItems: 'center', gap: 6,
                                padding: '4px 10px', background: T.surface,
                                borderRadius: 6, fontSize: 12, fontWeight: 600, color: T.blue
                            }}>
                                {sc?.name || id}
                                <button onClick={() => toggleScreener(id)} style={{
                                    background: 'none', border: 'none', color: T.textMuted,
                                    cursor: 'pointer', fontSize: 14, lineHeight: 1, padding: 0
                                }}>×</button>
                            </span>
                        )
                    })}
                </div>
            )}

            {/* Advanced Settings Panel */}
            {showAdvanced && selectedScreeners.length > 0 && (
                <div style={{
                    marginBottom: 16, padding: '16px',
                    background: T.surface, borderRadius: 8,
                    border: `1px solid ${T.border}`
                }}>
                    <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: T.navy }}>
                        Screener Parameters
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
                        {selectedScreeners.map(id => {
                            const sc = screeners.find(s => s.id === id)
                            const params = customParams[id] || {}
                            return (
                                <div key={id} style={{
                                    padding: 12, background: T.bg,
                                    borderRadius: 6, border: `1px solid ${T.border}`
                                }}>
                                    <h4 style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 700, color: T.blue }}>
                                        {sc?.name || id}
                                    </h4>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                                        {Object.entries(params).slice(0, 6).map(([key, val]) => (
                                            <div key={key}>
                                                <label style={{ fontSize: 10, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                                    {key.replace(/_/g, ' ')}
                                                </label>
                                                <input
                                                    type="number"
                                                    value={val as number}
                                                    onChange={(e) => updateParam(id, key, Number(e.target.value))}
                                                    style={{
                                                        width: '100%', padding: '6px 8px',
                                                        border: `1px solid ${T.border}`,
                                                        borderRadius: 4, fontSize: 12,
                                                        fontFamily: "'DM Mono', monospace"
                                                    }}
                                                />
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}

            {loading ? (
                <div style={{ textAlign: 'center', padding: 40, color: T.textMuted }}>
                    Loading stock list...
                </div>
            ) : runningScreener ? (
                <div style={{ textAlign: 'center', padding: 60, color: T.blue, fontWeight: 600 }}>
                    <div style={{ fontSize: 24, marginBottom: 12 }}>⚡</div>
                    Scanning 500 stocks...
                </div>
            ) : (
                <>
                    {screenerResults && (
                        <div style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            marginBottom: 16, padding: '12px 16px',
                            background: T.greenLight, borderRadius: 8,
                            border: `1px solid ${T.green}`
                        }}>
                            <span style={{ fontSize: 14, fontWeight: 600, color: T.green }}>
                                ✅ Found {screenerResults.length} stocks matching criteria
                            </span>
                            <button
                                onClick={handleBuildStrategy}
                                style={{
                                    padding: '8px 16px', borderRadius: 8, border: 'none',
                                    background: T.blue, color: '#fff',
                                    fontSize: 13, fontWeight: 600, cursor: 'pointer',
                                    transition: 'all 0.2s',
                                    display: 'flex', alignItems: 'center', gap: 6
                                }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.background = T.navy
                                    e.currentTarget.style.transform = 'translateY(-1px)'
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.background = T.blue
                                    e.currentTarget.style.transform = 'none'
                                }}
                            >
                                🚀 Build Strategy on These {screenerResults.length} Stocks
                            </button>
                        </div>
                    )}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                        gap: 12
                    }}>
                        {displayItems.map((item: any) => {
                            const sym = typeof item === 'string' ? item : item.symbol
                            const isScreenerMode = typeof item !== 'string'

                            // Extract notable metrics if in screener mode
                            const metrics = isScreenerMode ? Object.entries(item).filter(
                                ([k]) => !['symbol', 'screener', 'pass'].includes(k)
                            ).slice(0, 3) : []

                            return (
                                <Link
                                    key={sym}
                                    href={`/chart/${sym}`}
                                    style={{ textDecoration: 'none' }}
                                >
                                    <div style={{
                                        background: T.surface,
                                        padding: '14px 16px',
                                        borderRadius: 10,
                                        border: isScreenerMode ? `2px solid ${T.greenLight}` : `1px solid ${T.border}`,
                                        transition: 'all 0.15s',
                                        cursor: 'pointer',
                                    }}
                                        onMouseEnter={e => {
                                            e.currentTarget.style.borderColor = isScreenerMode ? T.green : T.blue
                                            e.currentTarget.style.background = isScreenerMode ? T.greenLight : T.blueLight
                                            e.currentTarget.style.transform = 'translateY(-2px)'
                                            e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.05)'
                                        }}
                                        onMouseLeave={e => {
                                            e.currentTarget.style.borderColor = isScreenerMode ? T.greenLight : T.border
                                            e.currentTarget.style.background = T.surface
                                            e.currentTarget.style.transform = 'none'
                                            e.currentTarget.style.boxShadow = 'none'
                                        }}
                                    >
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: isScreenerMode ? 12 : 4 }}>
                                            <div style={{ fontSize: 15, fontWeight: 800, color: T.navy }}>{sym}</div>
                                            <span style={{ fontSize: 11, color: T.blue, fontWeight: 600, background: T.blueLight, padding: '2px 8px', borderRadius: 4 }}>Chart →</span>
                                        </div>

                                        {isScreenerMode && (
                                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8, borderTop: `1px solid ${T.border}`, paddingTop: 8 }}>
                                                {metrics.map(([k, v]) => (
                                                    <div key={k}>
                                                        <div style={{ fontSize: 10, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                                            {k.replace(/_/g, ' ')}
                                                        </div>
                                                        <div style={{ fontSize: 13, fontWeight: 600, color: T.text, fontFamily: "'DM Mono', monospace" }}>
                                                            {formatMetric(k, v)}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </Link>
                            )
                        })}
                        {displayItems.length === 0 && (
                            <div style={{
                                gridColumn: '1 / -1', textAlign: 'center',
                                padding: 40, color: T.textMuted,
                                background: T.surface, borderRadius: 12, border: `1px dotted ${T.borderStrong}`
                            }}>
                                No stocks found matching logic or search
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    )
}

