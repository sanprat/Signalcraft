import { useState } from 'react'
import { Sparkles, Loader2, ArrowDown } from 'lucide-react'
import type { Condition } from '@/lib/types/strategy'
import { config, getAuthHeaders } from '@/lib/config'

interface ZenScriptQueryProps {
    onConditionsGenerated: (conditions: Condition[]) => void
}

export function ZenScriptQuery({ onConditionsGenerated }: ZenScriptQueryProps) {
    const [query, setQuery] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [successMsg, setSuccessMsg] = useState<string | null>(null)

    const handleGenerate = async () => {
        if (!query.trim()) return
        
        setIsLoading(true)
        setError(null)
        setSuccessMsg(null)
        
        try {
            const API_BASE = config.apiBaseUrl
            const res = await fetch(`${API_BASE}/api/strategy/v2/parse-query`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    ...getAuthHeaders() 
                },
                body: JSON.stringify({ query })
            })
            
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail || 'Failed to parse query')
            
            if (data.conditions && data.conditions.length > 0) {
                onConditionsGenerated(data.conditions)
                setSuccessMsg(`Successfully generated ${data.conditions.length} condition(s)!`)
                // clear after 3 seconds
                setTimeout(() => setSuccessMsg(null), 3000)
            } else {
                setError("Could not extract any valid trading rules from your text. Try being more specific like 'RSI is below 30'.")
            }
        } catch (err: any) {
            setError(err.message)
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden mb-6">
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-blue-100 px-5 py-4">
                <div className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-indigo-600" />
                    <h3 className="text-sm font-bold text-slate-800">ZenScript NLP Query</h3>
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-600">
                    Type your strategy rules in natural English. Our heuristic engine will automatically translate them into visual blocks below!
                </p>
            </div>
            
            <div className="p-5">
                <textarea
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g., Buy when the 14-period RSI drops below 30 and the price crosses above the 200 SMA."
                    className="min-h-[100px] w-full resize-y rounded-lg border border-slate-300 bg-white p-4 font-sans text-sm font-medium leading-relaxed text-slate-800 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 placeholder:text-slate-400"
                />
                
                {error && (
                    <div className="mt-3 rounded-lg bg-red-50 px-4 py-3 text-xs font-medium text-red-700 border border-red-100">
                        {error}
                    </div>
                )}
                
                {successMsg && (
                    <div className="mt-3 rounded-lg bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-700 border border-emerald-100 flex items-center gap-2">
                        <ArrowDown className="h-4 w-4" />
                        {successMsg}
                    </div>
                )}

                <div className="mt-4 flex justify-end">
                    <button
                        onClick={handleGenerate}
                        disabled={isLoading || !query.trim()}
                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50 shadow-sm"
                    >
                        {isLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Sparkles className="h-4 w-4" />
                        )}
                        Generate Visual Rules
                    </button>
                </div>
            </div>
        </div>
    )
}
