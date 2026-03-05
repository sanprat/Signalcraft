import { useState, useEffect } from 'react'
import Link from 'next/link'
import { config } from '@/lib/config'

const T = {
    bg: '#F8FAFC', surface: '#FFFFFF', surfaceHover: '#F1F5F9',
    border: '#E2E8F0', text: '#0F172A', textMid: '#475569', textMuted: '#94A3B8',
    blue: '#1D4ED8', blueLight: '#EFF6FF',
}

interface IndexInfo {
    symbol: string
    name: string
    description: string
}

const INDICES: IndexInfo[] = [
    { symbol: 'NIFTY', name: 'Nifty 50', description: 'NSE Benchmark Index' },
    { symbol: 'BANKNIFTY', name: 'Nifty Bank', description: 'NSE Bank Index' },
    { symbol: 'FINNIFTY', name: 'Nifty Financial Services', description: 'NSE Financial Services Index' },
    { symbol: 'GIFTNIFTY', name: 'Gift Nifty', description: 'GIFT City Index' },
]

export function IndicesView() {
    const [search, setSearch] = useState('')

    const filteredIndices = INDICES.filter(idx =>
        idx.symbol.toLowerCase().includes(search.toLowerCase()) ||
        idx.name.toLowerCase().includes(search.toLowerCase())
    )

    return (
        <div style={{ marginTop: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0 }}>Available Indices</h2>
                <div style={{ position: 'relative', width: 300 }}>
                    <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 14 }}>🔍</span>
                    <input
                        type="text"
                        placeholder="Search indices..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        style={{
                            width: '100%', padding: '10px 12px 10px 36px', borderRadius: 10,
                            border: `1px solid ${T.border}`, fontSize: 14, outline: 'none',
                            fontFamily: "'DM Sans', sans-serif"
                        }}
                    />
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
                {filteredIndices.map(idx => (
                    <div key={idx.symbol} style={{
                        background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12,
                        padding: 20, transition: 'all 0.15s', cursor: 'pointer',
                    }}
                        onMouseEnter={e => {
                            e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)';
                            e.currentTarget.style.borderColor = T.blue;
                        }}
                        onMouseLeave={e => {
                            e.currentTarget.style.boxShadow = 'none';
                            e.currentTarget.style.borderColor = T.border;
                        }}
                    >
                        <div style={{ fontSize: 12, fontWeight: 700, color: T.blue, letterSpacing: '0.8px', marginBottom: 4 }}>NSE INDEX</div>
                        <div style={{ fontSize: 18, fontWeight: 800, color: T.text, marginBottom: 2 }}>{idx.symbol}</div>
                        <div style={{ fontSize: 13, color: T.textMid, marginBottom: 16 }}>{idx.name}</div>
                        <div style={{ fontSize: 12, color: T.textMuted, marginBottom: 16 }}>{idx.description}</div>

                        <Link href={`/chart/${idx.symbol}`} style={{
                            display: 'block', width: '100%', padding: '10px', background: T.blueLight,
                            color: T.blue, borderRadius: 8, textAlign: 'center', fontSize: 13,
                            fontWeight: 700, textDecoration: 'none', transition: 'background 0.2s'
                        }}
                            onMouseEnter={e => e.currentTarget.style.background = '#DBEAFE'}
                            onMouseLeave={e => e.currentTarget.style.background = T.blueLight}
                        >
                            View Chart →
                        </Link>
                    </div>
                ))}
            </div>
            {filteredIndices.length === 0 && (
                <div style={{ textAlign: 'center', padding: 40, color: T.textMuted }}>
                    No indices found matching "{search}"
                </div>
            )}
        </div>
    )
}
